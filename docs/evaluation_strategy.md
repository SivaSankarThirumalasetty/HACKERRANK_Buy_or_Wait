# Evaluation Strategy

This document describes how to validate the system against the 25 public sample requests before running on the 250 evaluation requests.

---

## 1. Ground Truth from sample_requests.csv

The 25 solved examples in `dataset/sample_requests.csv` provide verifiable ground truth for:

| Field | Verifiable |
|---|---|
| `amount_safe_to_pay` | Yes — compare to within ±1 |
| `affordability_status` | Yes — exact match |
| `recommended_payment_method` | Yes — exact match |
| `payment_plan` | Yes — dates and amounts must match |
| `earliest_date_for_full_payment` | Yes — exact match |
| `spending_changes_needed` | Yes — event_id and amounts |
| `decision_explanation` | Partial — grounding facts must be present |

---

## 2. Self-Scoring Protocol

Before running the full 250 requests, run the system on requests 01–25 and compare to sample answers.

```python
def score_sample(predicted, ground_truth):
    scores = {}
    # Exact match fields
    for f in ['affordability_status', 'recommended_payment_method',
              'earliest_date_for_full_payment']:
        scores[f] = int(predicted[f] == ground_truth[f])
    
    # Near match for amounts (within 1 unit or ±0.01%)
    for f in ['amount_safe_to_pay']:
        expected = Decimal(ground_truth[f])
        actual = Decimal(predicted[f])
        scores[f] = int(abs(actual - expected) / max(expected, Decimal('1')) < Decimal('0.001'))
    
    # Payment plan: parse and compare date-amount pairs
    scores['payment_plan'] = compare_payment_plans(predicted['payment_plan'],
                                                   ground_truth['payment_plan'])
    
    # Spending changes: set comparison on event_ids and action types
    scores['spending_changes'] = compare_spending_changes(
        predicted['spending_changes_needed'],
        ground_truth['spending_changes_needed'])
    
    return sum(scores.values()) / len(scores)
```

---

## 3. Critical Validation Checks (Assertions)

Run these assertions on every generated row before writing to output.csv:

### 3.1 Hard Constraints (Failure = Disqualify)
```
assert 0 <= amount_safe_to_pay <= requested_amount
assert affordability_status in VALID_STATUSES
assert recommended_payment_method in VALID_METHODS
assert recommended_payment_method in user.payment_methods_user_will_consider \
    or recommended_payment_method == 'not_recommended'
assert len(spending_changes) <= 3
```

### 3.2 Logical Consistency
```
# affordable_now: earliest_date must be request_date
if affordability_status == 'affordable_now':
    assert earliest_date_for_full_payment == request_date

# not_affordable: payment_plan must be 'none'
if recommended_payment_method == 'not_recommended':
    assert payment_plan == 'none'
    assert earliest_date_for_full_payment == ''

# partial_payment: exactly two payments summing to requested_amount
if recommended_payment_method == 'partial_payment':
    payments = parse_payment_plan(payment_plan)
    assert len(payments) == 2
    assert sum(p.amount for p in payments) == requested_amount
    assert payments[0].date == request_date
    assert payments[0].amount == amount_safe_to_pay

# installments: must match an option in request_payment_options
if recommended_payment_method == 'installments':
    assert plan_matches_an_option(payment_plan, pay_opts)

# spending_changes: event must be flexible and non-protected
for change in spending_changes:
    event = events[change.event_id]
    assert event.flexibility != 'fixed'
    assert event.category not in user.expense_categories_to_protect
    assert is_recurring(event)
    if change.action == 'reduce_to':
        assert change.new_amount >= event.minimum_allowed_amount

# stop and reduce cannot target same event_id
stop_ids = {c.event_id for c in spending_changes if c.action == 'stop'}
reduce_ids = {c.event_id for c in spending_changes if c.action == 'reduce_to'}
assert stop_ids & reduce_ids == set()
```

### 3.3 Safety Simulation Verification
```
# For the recommended plan, re-run the full simulation and confirm
# the balance never drops below minimum_balance_to_keep
assert verify_plan_safety(plan, simulation, user.minimum_balance_to_keep)
```

---

## 4. Known Risk Areas (Priority Debugging)

These are the areas most likely to produce wrong answers based on the complexity of the rules:

| Risk | Priority | Description |
|---|---|---|
| Image OCR accuracy | **HIGH** | 16 blank events; wrong OCR = wrong financial state |
| Message parsing | **HIGH** | 216 messages; many patterns; Bahasa Indonesia messages |
| Recurrence detection | **HIGH** | Misidentify one-time as recurring = inflated expenses |
| Exchange rate lookup | **MEDIUM** | Sparse table; missing months; multi-hop needed |
| max_installment_months filter | **MEDIUM** | Incorrect span calculation rejects/accepts wrong plans |
| Pending debit reservation | **MEDIUM** | Missing reservation = falsely optimistic balance |
| Variable expense conservatism | **MEDIUM** | Using mean instead of 95th percentile |
| Payment plan date arithmetic | **MEDIUM** | Off-by-one in instalment schedule generation |
| Inter-account transfer double-counting | **MEDIUM** | Including both legs of a same-holder transfer |
| Prize/refund event classification | **LOW** | Most have clear message patterns |

---

## 5. Test Cases Derived from Sample Data

Key patterns observed in sample answers to verify:

| Sample | Key Decision Logic |
|---|---|
| request_01 | Full payment affordable today; simple baseline |
| request_02 | Installments only (user won't consider full); 3-payment plan; salary increase from message |
| request_03 | Wait until Nov; salary image needed for OCR (event_253) |
| request_04 | Wait until salary arrives; not enough today even with spending changes |
| request_05 | Not affordable; even stopping all flexible expenses won't help |
| request_06 | Full payment enabled by stopping streaming (spending change); uses stop: action |
| request_07 | Installments preferred by user who only considers installments |
| request_08 | Wait until April; EUR user with reduced salary from message |
| request_09 | Affordable now; full payment |
| request_10 | Not affordable; installments would exceed min balance |
| request_11 | Full payment with reduce_to spending change (food delivery) |
| request_12 | Installments (3-payment); user only considers partial+installments |
| request_13 | Wait until May; EUR user with tight margin |
| request_14 | Not affordable; can pay only ~EUR 597 today of EUR 5,414 total |
| request_15 | Not affordable; only EUR 83 safe |
| request_16 | Affordable now; image needed for event_1442 (INR housing) |
| request_17 | Installments; image needed for event_1545 |
| request_18 | Wait until September; EUR user |
| request_19 | Partial payment; image needed for event_1700; two payments |
| request_20 | Not affordable; image needed for event_1786 (pending debit) |
| request_21 | Full payment after stop+reduce spending changes |
| request_22 | Installments (EUR user, 3 payments) |
| request_23 | Wait until July |
| request_24 | Not affordable; only INR 13,420 safe |
| request_25 | Not affordable; IDR deposit too large |

---

## 6. Regression Test Matrix

After any code change, re-run these sample checks to catch regressions:

- [ ] request_02: Installment plan dates and amounts exact match
- [ ] request_03: OCR amount from image_01 = IDR 4,365,000
- [ ] request_06: stop:event_476 appears in spending_changes
- [ ] request_11: reduce_to:event_989:665950 appears
- [ ] request_19: Partial payment with two payments summing correctly
- [ ] request_21: Two spending changes both appear

---

## 7. Submission Checklist

Before submitting:
- [ ] output.csv has exactly 250 rows (request_26 to request_275) plus header
- [ ] All `amount_safe_to_pay` values satisfy 0 ≤ value ≤ requested_amount
- [ ] All installment plans exactly match a row in request_payment_options
- [ ] All spending changes target flexible, non-protected, recurring events
- [ ] evaluation/usage_report.md exists and includes all required fields
- [ ] No API keys in code.zip
- [ ] code.zip includes README with run instructions
- [ ] log.txt is available as chat_transcript
