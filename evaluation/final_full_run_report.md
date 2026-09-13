# Final Full-Dataset Reproduction Report

**Run Execution Timestamp:** 2026-09-13T16:43:47+05:30  
**Environment:** Clean execution (prior outputs, reports, and bytecode caches purged)  
**Execution Entrypoint:** 
un.py  
**Dataset Path:** dataset/  

---

## 1. Executive Summary

This report documents the clean reproduction run of the complete production pipeline for HackerRank Orchestrate: **Buy or Wait?**. All 250 evaluation requests were executed from scratch against the actual workspace dataset, with all 17 competition rules validated. Following execution, an independent revalidation audit was performed directly on output.csv, confirming 100% compliance with zero defects.

---

## 2. Ingested Dataset Inventory

All counts are directly measured from disk during the reproduction run:

| Dataset Entity | File Path | Actual Record Count | Notes |
| :--- | :--- | :--- | :--- |
| **Evaluation Requests** | dataset/requests.csv | **250** | 
equest_26 through 
equest_275 |
| **Financial Profiles** | dataset/financial_profiles.csv | **275** | Across 5 currencies (INR, EUR, IDR, USD, ZAR) |
| **Financial Events** | dataset/financial_events.csv | **25,342** | Settled, scheduled, pending, unrealized, failed, cancelled |
| **Payment Options** | dataset/request_payment_options.csv | **790** | 2 to 4 options per request |
| **Message Evidence** | dataset/messages.csv | **215** | Deterministic regex-based financial amendments |
| **Image Evidence Records** | dataset/images.csv | **16** | Pre-extracted verified OCR amount anchors |
| **Exchange Rates** | dataset/exchange_rates.csv | **134** | Dated FX pairs with deterministic multi-hop graph routing |

---

## 3. End-to-End Pipeline Telemetry

| Pipeline Stage | Scope | Measured Runtime | Sub-task Detail |
| :--- | :--- | :--- | :--- |
| **Step 1: Data Loading** | 7 CSV files parsed into typed domain models | **0.4053 s** | Exact Decimal parsing, date parsing |
| **Step 2: Normalization & Evidence** | 25,342 events normalized + 215 messages parsed | **0.0922 s** | Normalization: 0.0771s; Evidence: 0.0151s |
| **Step 3: Decision Engine & 90-Day Simulation** | 250 requests evaluated through full cash-flow simulation | **2.8966 s** | **0.0116 s / request** (11.6 ms/request) |
| **Step 4: Strict 17-Rule Validation** | In-pipeline comprehensive contest rule checking | **0.0163 s** | 17/17 contest rules verified |
| **Step 5: Output Generation** | Atomically writing output files & reports | **0.0050 s** | Header verification & disk flush |
| **Total Pipeline Runtime** | **Full End-to-End Execution** | **3.416 s** | **~13.7 ms total latency / request** |

---

## 4. Output Reconciliation & Independent Audit

An independent secondary validator script was executed directly against output.csv without reusing pipeline state:

| Audit Criterion | Expected | Measured / Observed | Audit Status |
| :--- | :--- | :--- | :--- |
| **Input Requests Count** | 250 | 250 | **MATCH** |
| **Output Rows Count** | 250 | 250 | **MATCH** |
| **Request ID Sequence** | 
equest_26 ... 
equest_275 | Identical 1-to-1 ordering | **MATCH** |
| **Duplicate Request IDs** | 0 | 0 | **PASSED** |
| **Missing Request IDs** | 0 | 0 | **PASSED** |
| **CSV Output Schema** | 8 exact columns in required order | 
equest_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation | **EXACT MATCH** |
| **Monetary Constraints** | \(0 \le \text{amount\_safe\_to\_pay} \le \text{requested\_amount}\) | All 250 rows strictly bounded | **PASSED** |
| **Payment Plans** | Chronological dates, exact sums, format YYYY-MM-DD:amount or 
one | All 250 plans compliant | **PASSED** |
| **Deadlines** | On-time completion for recommended plans | No completion date violates desired_completion_date | **PASSED** |
| **Spending Changes** | Max 3, flexible only, non-protected, user willingness respected | All rows with spending changes strictly compliant | **PASSED** |
| **Validation Errors** | 0 | **0** | **100% PASSED** |

---

## 5. Decision & Category Distributions

### Affordability Status Distribution

`	ext
  affordable_now:       59  (23.6%)
  affordable_with_plan: 59  (23.6%)
  affordable_later:     48  (19.2%)
  not_affordable:       84  (33.6%)
  ---------------------------------
  Total Requests:      250  (100.0%)
`

### Recommended Payment Method Distribution

`	ext
  full_payment:         61  (24.4%)
  installments:         49  (19.6%)
  partial_payment:       8   (3.2%)
  wait:                 48  (19.2%)
  not_recommended:      84  (33.6%)
  ---------------------------------
  Total Requests:      250  (100.0%)
`

---

## 6. Output Artifact Verification

- **Primary Output CSV:** d:\HACKATHON\hackerrank-orchestrate-september26-main\output.csv
- **Validation Report:** d:\HACKATHON\hackerrank-orchestrate-september26-main\evaluation\validation_report.md
- **Performance Report:** d:\HACKATHON\hackerrank-orchestrate-september26-main\evaluation\performance_report.md
- **Usage Report:** d:\HACKATHON\hackerrank-orchestrate-september26-main\evaluation\usage_report.md
