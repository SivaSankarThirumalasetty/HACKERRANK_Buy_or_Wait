# Mathematical Audit Report: amount_safe_to_pay

## 1. Executive Summary

- Evaluation Requests Audited: 250
- Sample Requests Audited: 25
- Total Requests Tested: 275
- Exact Matches (Cent-for-Cent): 275 / 275 (100.0%)
- Mismatches / Divergences: 0

## 2. Mathematical Definition

amount_safe_to_pay is defined as:
max x such that 0 <= x <= requested_amount
and for EVERY forecast day d in [request_date, request_date + 90 days]:
closing_balance_without_request[d] - x >= minimum_balance_to_keep

Equivalently:
margin[d] = closing_balance_without_request[d] - minimum_balance_to_keep
x = clamp(floor_to_cent(min_{d in horizon} margin[d]), 0, requested_amount)

## 3. Independent Reference Implementation

File: 	ests/fixtures/reference_calculator.py
- Completely separate implementation loop without calling calculate_amount_safe_to_pay().
- Pending debit reserves handled at Day 0 in home currency using dated FX.
- Pending credits excluded from cash balance until confirmed settlement.
- Cancelled, failed, unrealized, and non-cash events excluded.
- Scheduled confirmed events included on settlement_date.
- Canonical recurring streams projected forward conservatively.
- Foreign currencies converted using dated exchange rate tables.
- Message amendments applied before forecasting.
- Spending changes excluded (measuring baseline capacity before changes).

## 4. Evaluation Distribution

- Full Amount Safe (x == requested_amount): 82
- Partial Amount Safe (0 < x < requested_amount): 132
- Zero Safe (x == 0): 36

## 5. Verification Table (First 20 Evaluation Requests)

| Request ID | User ID | Requested Amount | Reference Safe | Production Safe | Engine Decision Safe | Min Margin Date | Match |
|:---|:---|:---|:---|:---|:---|:---|:---|
| request_26 | user_26 |  15656000 | 15656000 | 15656000 | 15656000 | 2025-08-03 | EXACT |
| request_27 | user_27 |  6670 | 6670 | 6670 | 6670 | 2026-07-05 | EXACT |
| request_28 | user_28 |  1302.4 | 0 | 0 | 0 | 2024-09-05 | EXACT |
| request_29 | user_29 |  51524 | 12146.07 | 12146.07 | 12146.07 | 2026-02-02 | EXACT |
| request_30 | user_30 |  775.2 | 775.2 | 775.2 | 775.2 | 2026-04-06 | EXACT |
| request_31 | user_31 |  18164000 | 2568593.04 | 2568593.04 | 2568593.04 | 2024-09-14 | EXACT |
| request_32 | user_32 |  40018 | 17672.94 | 17672.94 | 17672.94 | 2025-02-11 | EXACT |
| request_33 | user_33 |  118000 | 46044.76 | 46044.76 | 46044.76 | 2026-01-13 | EXACT |
| request_34 | user_34 |  129400 | 129400 | 129400 | 129400 | 2024-12-04 | EXACT |
| request_35 | user_35 |  212000 | 25401.67 | 25401.67 | 25401.67 | 2025-11-13 | EXACT |
| request_36 | user_36 |  3954 | 736.96 | 736.96 | 736.96 | 2026-07-09 | EXACT |
| request_37 | user_37 |  14649000 | 0 | 0 | 0 | 2024-06-03 | EXACT |
| request_38 | user_38 |  971.3 | 264.82 | 264.82 | 264.82 | 2025-08-12 | EXACT |
| request_39 | user_39 |  208600 | 150709.72 | 150709.72 | 150709.72 | 2026-04-13 | EXACT |
| request_40 | user_40 |  1290.3 | 332.46 | 332.46 | 332.46 | 2024-06-12 | EXACT |
| request_41 | user_41 |  38760000 | 11614770.23 | 11614770.23 | 11614770.23 | 2025-11-13 | EXACT |
| request_42 | user_42 |  52100 | 0 | 0 | 0 | 2026-04-03 | EXACT |
| request_43 | user_43 |  43339000 | 9868266.98 | 9868266.98 | 9868266.98 | 2024-09-12 | EXACT |
| request_44 | user_44 |  95800 | 37186.61 | 37186.61 | 37186.61 | 2025-02-11 | EXACT |
| request_45 | user_45 |  21983000 | 4339787.52 | 4339787.52 | 4339787.52 | 2026-07-13 | EXACT |

## 6. Automated Mathematical Tests

The test suite 	ests/test_amount_safe_to_pay_mathematical.py executes on every build:
- Verifies 250 evaluation requests against reference calculator
- Verifies 25 sample requests against reference calculator
- Asserts that balance after paying amount_safe_to_pay never breaches minimum_balance_to_keep on any of the 91 forecast days
- Asserts that if amount_safe_to_pay is 0, a cash deficit existed on at least one forecast day

**Status**: ALL 275 REQUESTS PASS WITH ZERO DEFECTS.