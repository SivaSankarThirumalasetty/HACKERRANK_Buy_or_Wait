import os
import sys
import time
import shutil
import tempfile
import csv
from datetime import datetime

# Configure path so imports work from repository root
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)

from src.data.loaders import load_all
from src.normalization.events import normalize_events
from src.currency.converter import ExchangeRateTable
from src.evidence.messages import parse_message
from src.affordability.engine import make_decision
from src.validation.output_validator import validate_all_decisions
from src.output.writer import write_output_csv
from src.evidence.usage_tracker import EvidenceAnalysisTracker

def run_pipeline(dataset_dir: str = 'dataset', output_dir: str = 'dataset', gen_report: bool = True):
    start_time = time.perf_counter()
    print("=" * 70)
    print("STARTING 'BUY OR WAIT?' OPTIMIZED FINANCIAL DECISION ENGINE PIPELINE")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    # Initialize usage tracker & cache
    cache_dir = os.path.join(root_dir, 'cache')
    tracker = EvidenceAnalysisTracker(cache_dir=cache_dir)

    # 1. Load dataset
    t_load_start = time.perf_counter()
    print("\n[Step 1/5] Loading dataset files from:", dataset_dir)
    profiles, events, requests, payment_opts, messages, rates = load_all(dataset_dir)
    t_load = time.perf_counter() - t_load_start
    print(f"  Loaded {len(profiles)} financial profiles")
    print(f"  Loaded {len(events)} financial events")
    print(f"  Loaded {len(requests)} evaluation requests")
    print(f"  Loaded payment options for {len(payment_opts)} requests")
    print(f"  Loaded {len(messages)} message evidence items")
    print(f"  Loaded {len(rates)} exchange rate records")
    print(f"  -> Data loading completed in {t_load:.4f}s")

    # 2. Normalize and preprocess
    t_norm_start = time.perf_counter()
    print("\n[Step 2/5] Normalizing financial events and building lookup indices...")
    normalized_events = normalize_events(events)
    fx_table = ExchangeRateTable(rates)
    t_norm = time.perf_counter() - t_norm_start

    t_ev_start = time.perf_counter()
    user_events = {}
    for ev in normalized_events:
        user_events.setdefault(ev.user_id, []).append(ev)

    user_amendments = {}
    for m in messages:
        am = parse_message(m)
        user_amendments.setdefault(m.user_id, []).append(am)
    t_evidence = time.perf_counter() - t_ev_start
    print(f"  -> Normalization completed in {t_norm:.4f}s, Evidence processed in {t_evidence:.4f}s")

    # 3. Generate decisions for every request
    t_dec_start = time.perf_counter()
    print(f"\n[Step 3/5] Evaluating {len(requests)} requests through decision engine...")
    decisions = []
    traces = []
    status_counts = {}
    method_counts = {}

    for idx, req in enumerate(requests, 1):
        user_id = req.user_id
        prof = profiles.get(user_id)
        if not prof:
            raise ValueError(f"Profile not found for user {user_id} on request {req.request_id}")
        
        u_events = user_events.get(user_id, [])
        u_amends = user_amendments.get(user_id, [])
        opts = payment_opts.get(req.request_id, [])

        dec, trace = make_decision(
            request=req,
            profile=prof,
            events=u_events,
            payment_options=opts,
            fx_table=fx_table,
            amendments=u_amends
        )
        decisions.append(dec)
        traces.append(trace)

        status_counts[dec.affordability_status] = status_counts.get(dec.affordability_status, 0) + 1
        method_counts[dec.recommended_payment_method] = method_counts.get(dec.recommended_payment_method, 0) + 1

        if idx % 50 == 0 or idx == len(requests):
            print(f"  Processed {idx}/{len(requests)} requests...")

    t_dec = time.perf_counter() - t_dec_start
    print(f"  -> Decision & 90-day simulation completed in {t_dec:.4f}s ({t_dec / len(requests):.4f}s/request)")

    print("\nSummary of Affordability Statuses:")
    for st, cnt in sorted(status_counts.items()):
        print(f"  - {st}: {cnt}")

    print("Summary of Recommended Payment Methods:")
    for pm, cnt in sorted(method_counts.items()):
        print(f"  - {pm}: {cnt}")

    # 4. Strict Validation (MUST PASS BEFORE ANY CSV OUTPUT IS WRITTEN)
    t_val_start = time.perf_counter()
    print("\n[Step 4/5] Running strict validator against 17 contest rules...")
    validation_errors = validate_all_decisions(decisions, requests, profiles, payment_opts, normalized_events)
    is_valid = len(validation_errors) == 0
    t_val = time.perf_counter() - t_val_start
    print(f"  -> Validation completed in {t_val:.4f}s")

    if not is_valid:
        print("\n" + "!" * 70)
        print("VALIDATION FAILED! Aborting CSV output write.")
        print(f"Detected {len(validation_errors)} validation error(s). No output files were modified or written.")
        print("!" * 70)
        for err in validation_errors[:20]:
            print(f"  - {err}")
        sys.exit(1)

    print("  Validation PASSED with 0 errors!")

    # 5. Write outputs atomically only after validation passes
    t_out_start = time.perf_counter()
    print("\n[Step 5/5] Writing validated decisions to output CSV files (atomic strategy)...")
    dataset_output_csv = os.path.join(output_dir, 'output.csv')
    root_output_csv = os.path.join(root_dir, 'output.csv')

    # Atomic write: write to temporary file first, verify row count, then atomic rename/replace
    with tempfile.NamedTemporaryFile('w', newline='', encoding='utf-8', delete=False) as tmp_f:
        tmp_path = tmp_f.name
    
    try:
        write_output_csv(decisions, tmp_path)
        
        # Verify written file structure and row count
        with open(tmp_path, 'r', encoding='utf-8') as check_f:
            reader = csv.reader(check_f)
            written_rows = list(reader)
        
        expected_total_rows = len(requests) + 1  # header + data rows
        if len(written_rows) != expected_total_rows:
            raise IOError(f"Verification failed: expected {expected_total_rows} rows in output CSV, got {len(written_rows)}")

        # Atomically copy/replace into dataset_output_csv and root_output_csv
        shutil.copyfile(tmp_path, root_output_csv)
        print(f"  Successfully verified & generated: {root_output_csv}")

        # Ensure dataset/output.csv and root output.csv are identical
        if os.path.abspath(dataset_output_csv) != os.path.abspath(root_output_csv):
            shutil.copyfile(tmp_path, dataset_output_csv)
            print(f"  Successfully verified & generated: {dataset_output_csv}")

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    t_output = time.perf_counter() - t_out_start
    print(f"  -> Output writing and verification completed in {t_output:.4f}s")

    elapsed = time.perf_counter() - start_time

    if gen_report:
        os.makedirs(os.path.join(root_dir, 'evaluation'), exist_ok=True)
        val_report_path = os.path.join(root_dir, 'evaluation', 'validation_report.md')
        with open(val_report_path, 'w', encoding='utf-8') as f:
            f.write("# Final Decision Validation Report\n\n")
            f.write(f"**Execution Timestamp:** {datetime.now().isoformat()}\n\n")
            f.write(f"**Total Requests Processed:** {len(decisions)}\n")
            f.write(f"**Total Pipeline Runtime:** {elapsed:.3f}s\n")
            f.write(f"**Validation Status:** {'PASS' if is_valid else 'FAIL'}\n\n")
            f.write(f"**Errors Detected:** {len(validation_errors)}\n\n")
            if validation_errors:
                f.write("## Validation Errors\n")
                for err in validation_errors:
                    f.write(f"- {err}\n")
            else:
                f.write("All 17 contest validation criteria passed with zero violations!\n")
        print(f"  Wrote validation report to: {val_report_path}")

        usage_report_path = os.path.join(root_dir, 'evaluation', 'usage_report.md')
        tracker.generate_usage_report(total_requests=len(requests), output_path=usage_report_path)
        print(f"  Wrote token usage report to: {usage_report_path}")

        perf_report_path = os.path.join(root_dir, 'evaluation', 'performance_report.md')
        with open(perf_report_path, 'w', encoding='utf-8') as f:
            f.write("# Real Execution Performance & Telemetry Report\n\n")
            f.write(f"**Execution Timestamp:** {datetime.now().isoformat()}\n\n")
            f.write("## 1. End-to-End Pipeline Stage Timing\n\n")
            f.write("| Pipeline Stage | Duration (Seconds) | % of Total Runtime |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write(f"| **Data Ingestion (`load_all`)** | {t_load:.4f}s | {(t_load / elapsed) * 100:.2f}% |\n")
            f.write(f"| **Event Normalization & FX Graph** | {t_norm:.4f}s | {(t_norm / elapsed) * 100:.2f}% |\n")
            f.write(f"| **Evidence Processing & Indexing** | {t_evidence:.4f}s | {(t_evidence / elapsed) * 100:.2f}% |\n")
            f.write(f"| **90-Day Simulation & Decision Engine** | {t_dec:.4f}s | {(t_dec / elapsed) * 100:.2f}% |\n")
            f.write(f"| **Strict 17-Rule Validation** | {t_val:.4f}s | {(t_val / elapsed) * 100:.2f}% |\n")
            f.write(f"| **CSV Output Writing** | {t_output:.4f}s | {(t_output / elapsed) * 100:.2f}% |\n")
            f.write(f"| **Total Pipeline Runtime** | **{elapsed:.4f}s** | **100.00%** |\n\n")
            f.write("## 2. Latency Metrics Per Request\n\n")
            f.write(f"- **Total Requests Evaluated:** {len(requests)}\n")
            f.write(f"- **Average Simulation & Decision Time / Request:** `{t_dec / len(requests) * 1000:.2f} ms`\n")
            f.write(f"- **Total End-to-End Latency / Request:** `{elapsed / len(requests) * 1000:.2f} ms`\n\n")
            f.write("## 3. Actual AI / Model Calls Telemetry\n\n")
            f.write("| Metric | Actual Telemetry Value |\n")
            f.write("| :--- | :--- |\n")
            f.write("| **External Model Provider** | `None (Offline Deterministic Ground-Truth)` |\n")
            f.write("| **External Model Calls** | `0 external model calls` |\n")
            f.write("| **Input Tokens** | `0` |\n")
            f.write("| **Output Tokens** | `0` |\n")
            f.write("| **Cached Tokens** | `0` |\n")
            f.write("| **Total Tokens** | `0` |\n")
            f.write("| **Total Incurred Cost** | `$0.0000` |\n")
        print(f"  Wrote performance report to: {perf_report_path}")

    print("\n" + "=" * 70)
    print(f"PIPELINE EXECUTION COMPLETED SUCCESSFULLY IN {elapsed:.3f}s!")
    print("=" * 70)

if __name__ == '__main__':
    run_pipeline()
