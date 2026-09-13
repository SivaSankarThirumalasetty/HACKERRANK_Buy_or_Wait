# Buy or Wait? — System Architecture

## Overview

The system is an AI-powered financial affordability agent. Given a purchase or payment request for a specific user, it reconstructs that user's full financial position, forecasts the next 90 days of cash flow, evaluates every eligible payment plan, and outputs a deterministic, auditable recommendation in the exact format required by the HackerRank evaluator.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                     │
│  dataset/requests.csv  →  per-request parameters + user_id             │
│  dataset/financial_profiles.csv  →  user-level settings & preferences  │
│  dataset/financial_events.csv    →  25,343 raw transaction rows         │
│  dataset/exchange_rates.csv      →  135 dated currency conversion rows  │
│  dataset/request_payment_options.csv → 791 payment option rows          │
│  dataset/messages.csv            →  216 contextual messages             │
│  dataset/images.csv + media/     →  16 images (receipts / payslips)     │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  PREPROCESSING PIPELINE  (Module 1)                     │
│  • Load & index all CSVs into memory keyed by user_id / request_id     │
│  • Image OCR  →  fill blank amounts in financial_events                 │
│  • Currency normalisation  →  convert all amounts to home_currency      │
│  • Event lifecycle resolution  →  discard cancelled/failed/unrealized   │
│  • Message parsing  →  apply payroll/lease/refund/prize amendments      │
│  • Recurrence detection  →  identify periodic income & expense series   │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              FINANCIAL STATE BUILDER  (Module 2)                        │
│  • Starting balance = current_available_balance from profile            │
│  • Subtract: pending debits (reserved)                                  │
│  • Build recurring cashflow model: income dates + expense dates         │
│  • Project: 90-day day-by-day balance timeline from request_date        │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              AMOUNT_SAFE_TO_PAY CALCULATOR  (Module 3)                  │
│  • Binary-search the max single payment on request_date                 │
│    that never drops balance below minimum_balance_to_keep               │
│    across 90 days of projected cashflow                                 │
│  • Cap at requested_amount                                              │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              PLAN GENERATOR  (Module 4)                                 │
│  Generates all candidate plans in priority order:                       │
│  1. full_payment  (if user accepts full_payment)                        │
│  2. partial_payment  (if user accepts partial_payment, allowed, valid)  │
│  3. installments  (for each option in request_payment_options)          │
│  4. wait  (scan future dates for earliest safe full_payment)            │
│  5. spending_changes  (try stop/reduce flexible events, retry plans)    │
│  6. not_recommended  (fallback)                                         │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              PLAN RANKER & SELECTOR  (Module 5)                         │
│  Applies the spec-mandated ranking:                                     │
│  1. Completes by desired_completion_date                                │
│  2. No spending changes                                                 │
│  3. Minimize total amount paid                                          │
│  4. Start earlier                                                       │
│  5. Fewer payments                                                      │
│  6. Lowest payment_option_id                                            │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              VERIFIER  (Module 6)                                       │
│  • Re-runs 90-day simulation with chosen plan injected                  │
│  • Asserts balance ≥ minimum_balance_to_keep at every step             │
│  • Validates all output constraints before serialising                  │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              EXPLANATION GENERATOR  (Module 7) — LLM-optional           │
│  • Constructs decision_explanation from structured facts                │
│  • If LLM available: pass facts + template → concise summary            │
│  • If LLM unavailable: deterministic template fill                      │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              OUTPUT WRITER  (Module 8)                                  │
│  • Serialises one row per request to output.csv                         │
│  • Writes evaluation/usage_report.md                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack (Recommended)

| Concern | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | Spec recommends it; rich stdlib |
| CSV parsing | `csv` / `pandas` | `pandas` for join speed on 25K events |
| Image OCR | Google Gemini Vision / GPT-4o / pytesseract | 16 images; multimodal LLM preferred for accuracy |
| LLM calls | Google Gemini 1.5 Pro / Flash | For OCR + explanation; batched to minimise cost |
| Financial arithmetic | Python `decimal.Decimal` | No float rounding errors in currency |
| Forecasting | Pure Python timeline simulation | Deterministic; no external deps |
| Packaging | `zipfile` stdlib | Produce code.zip reproducibly |

---

## Execution Flow

```
main.py
  ├── DataLoader.load_all()          # Parse all 9 CSVs into memory
  ├── ImageOCR.fill_blank_amounts()  # For 16 images
  ├── for request in requests.csv:
  │   ├── UserContext.build(user_id, request_id)
  │   │   ├── filter events by user_id
  │   │   ├── apply message amendments
  │   │   ├── normalise currencies
  │   │   └── detect recurring patterns
  │   ├── Forecaster.simulate(context, request_date, horizon=90)
  │   ├── SafePayCalculator.compute(simulation, requested_amount)
  │   ├── PlanGenerator.generate_all(context, simulation)
  │   ├── PlanRanker.select_best(plans, preferences, deadline)
  │   ├── Verifier.validate(best_plan, simulation)
  │   ├── ExplanationGenerator.generate(best_plan, context)
  │   └── OutputRow.serialize()
  └── write output.csv + usage_report.md
```

---

## Concurrency / Batching Strategy

- All CSV data is pre-loaded once at startup (O(1) per request after that).
- LLM calls (OCR + explanation) are batched and cached.
- 16 images → 16 OCR calls at start; results are cached and never re-called.
- 250 explanations → batch via LLM API (if used); otherwise template-generated.
- Deterministic financial math never requires an LLM call.

---

## Dependency Graph

```
requests.csv
    │
    ├── financial_profiles.csv  (user_id)
    ├── financial_events.csv    (user_id)
    │       └── images.csv      (related_event_id)  →  media/images/*.png
    ├── messages.csv            (user_id / request_id / related_event_id)
    ├── exchange_rates.csv      (rate_date × currency_pair)
    └── request_payment_options.csv (request_id)
```
