# Data Model

All data relationships, field semantics, and cardinalities derived from direct inspection of the dataset.

---

## 1. financial_profiles.csv — User-Level Settings

**Primary key:** `user_id`
**One row per user (277 rows = 275 users + header + 1 blank).**

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | FK to all other tables |
| `home_currency` | enum | `INR` / `ZAR` / `IDR` / `USD` / `EUR` |
| `current_available_balance` | decimal | Starting balance in home_currency |
| `minimum_balance_to_keep` | decimal | Hard floor; never breach |
| `financial_priorities` | pipe-delimited | e.g. `education\|debt_repayment` |
| `expense_categories_to_protect` | pipe-delimited | Categories NEVER available for spending changes |
| `expense_categories_user_is_willing_to_reduce` | pipe-delimited | May use `reduce_to:` action |
| `expense_categories_user_is_willing_to_stop` | pipe-delimited | May use `stop:` action |
| `payment_methods_user_will_consider` | pipe-delimited | Subset of: `full_payment`, `partial_payment`, `installments` |
| `max_installment_months` | int or blank | Blank = will not consider installments at all |

**Important derived rules:**
- `wait` is valid only when `full_payment` is in `payment_methods_user_will_consider`.
- If `max_installment_months` is blank, never recommend installments regardless of options.
- An installment plan is rejected if `number_of_payments × payment_frequency_days / 30 > max_installment_months` (approximate; use calendar comparison of first and last payment date).
- `stop` and `reduce` are mutually exclusive on the same `event_id`.

---

## 2. requests.csv — One Row Per Evaluation Request

**Primary key:** `request_id`
**250 rows (request_26 … request_275 plus sample rows request_01 … request_25).**

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | FK to request_payment_options |
| `user_id` | string | FK to profiles / events / messages |
| `request_date` | date | Date of evaluation; day-zero of forecast |
| `request_type` | enum | `purchase`, `travel`, `education`, `family_transfer`, `debt_repayment`, `investment`, `housing`, `emergency_expense`, `other` |
| `requested_amount` | decimal | In home_currency |
| `desired_completion_date` | date | Deadline for the full payment plan |
| `allows_partial_payment` | bool | `true` / `false` — request-side permission for partial payment |
| `request_text` | string | Natural language; do NOT parse for financial amounts |

**80 of 250 requests allow partial payment.**

---

## 3. financial_events.csv — Transaction / Cashflow History

**Primary key:** `event_id`
**25,343 rows. Keyed by `user_id`.**

| Field | Type | Notes |
|---|---|---|
| `event_id` | string | Unique per row |
| `user_id` | string | FK |
| `event_type` | enum | `expense`, `income`, `subscription`, `debt_payment`, `investment_purchase`, `investment_sale`, `investment_valuation`, `refund` |
| `description` | string | Human label; not parsed programmatically |
| `category` | string | `rent`, `utilities`, `groceries`, `dining`, `transport`, `education`, `healthcare`, `insurance`, `housing`, `entertainment`, `gym`, `shopping`, `streaming`, `cloud_storage`, `music_subscription`, `delivery_membership`, `debt_repayment`, `salary`, `investment`, etc. |
| `direction` | enum | `debit`, `credit`, `non_cash` |
| `amount` | decimal or **blank** | **Blank = must read from linked image** |
| `currency` | enum | May differ from home_currency |
| `event_date` | date | When transaction was initiated |
| `settlement_date` | date | When it clears; use this for cash-flow timing |
| `status` | enum | `settled`, `pending`, `scheduled`, `cancelled`, `failed`, `unrealized` |
| `linked_event_id` | string or blank | References an earlier event in the same lifecycle |
| `flexibility` | enum | `fixed`, `reducible`, `stoppable`, `reducible_or_stoppable` |
| `minimum_allowed_amount` | decimal or blank | Floor for `reduce_to:` action |

### 3.1 Status Semantics

| Status | Cash-flow treatment |
|---|---|
| `settled` | **Include** — actual cash movement occurred |
| `pending` | **Reserve debit; exclude credit** — debit committed, credit not yet confirmed |
| `scheduled` | **Include as confirmed** — same as settled for future dates |
| `cancelled` | **Exclude** — transaction voided |
| `failed` | **Exclude** — transaction never processed |
| `unrealized` | **Exclude** — non-cash valuation change only |

### 3.2 Direction Semantics

| Direction | Treatment |
|---|---|
| `debit` | Cash outflow (negative) |
| `credit` | Cash inflow (positive) |
| `non_cash` | **Always exclude** — investment mark-to-market, no cash movement |

### 3.3 Event Type Semantics

| Type | Treatment |
|---|---|
| `expense`, `subscription`, `debt_payment` | Outflow; include if status ∈ {settled, pending, scheduled} |
| `income` | Inflow; include only if status ∈ {settled, scheduled}; **never pending** |
| `refund` | Inflow; include only if settled |
| `investment_purchase` | Outflow; treat as debit if settled |
| `investment_sale` | Inflow; treat as credit if settled |
| `investment_valuation` | **Always exclude** (non_cash + unrealized) |

### 3.4 Blank Amount Rule

16 events have `amount = ""`. All 16 have a matching `related_event_id` entry in `images.csv`. For each blank, locate the linked image file at `dataset/media/images/<image_id>.png` and extract the amount via OCR. Never substitute zero or any other default.

### 3.5 Linked Events

`linked_event_id` pointing to an earlier event does NOT automatically inherit its status or amount. Each row is evaluated on its own `status` and `amount`. The link exists to trace the lifecycle (e.g. `cancelled` authorization → `settled` actual charge; `investment_purchase` → `investment_valuation`).

### 3.6 Recurrence Detection

Do NOT forecast recurrence from raw intervals alone. Recurrence is inferred when:
- Two or more settled/historical events of the same user, category, event_type share the same periodic description/amount pattern.
- The pattern is confirmed by recent history (≥ 2 occurrences within 3 months before request_date).
- Income recurrence is confirmed only from message amendments or explicit `scheduled` events.

**Conservative rule:** If historical data is ambiguous, model the most expensive plausible recurring scenario.

---

## 4. exchange_rates.csv — Fixed Dated Rates

**135 rows. No primary key; composite key = (`rate_date`, `from_currency`, `to_currency`).**

| Field | Notes |
|---|---|
| `rate_date` | Monthly snapshot date |
| `from_currency` | Source |
| `to_currency` | Target |
| `rate` | Multiply `amount × rate` to convert |

### 4.1 Rate Lookup Rules

- Use the `rate_date` that matches the `settlement_date` of the event (not `event_date`).
- If no exact match: use the closest available rate on or before the settlement date.
- Currency pairs NOT in the table require multi-hop conversion: e.g. ZAR→INR = ZAR→USD + USD→INR (both rates must exist).
- All input/output amounts must be in the user's `home_currency`.

### 4.2 Coverage Gaps

The table is sparse. Notable gaps:
- EUR↔ZAR not always present (use EUR→USD→ZAR via two hops when needed).
- IDR↔ZAR, IDR↔EUR, IDR↔INR not directly available; always go through USD.
- Some months (e.g. June/July 2024) are missing EUR↔ZAR; nearest prior rate applies.

---

## 5. request_payment_options.csv — Seller Options Per Request

**791 rows. Composite key = `payment_option_id` (unique). 2–4 options per request.**

| Field | Notes |
|---|---|
| `payment_option_id` | Unique option ID; used as tiebreaker in ranking |
| `request_id` | FK to requests |
| `payment_method` | `full_payment` or `installments` |
| `payment_amount` | Per-instalment amount in home_currency |
| `number_of_payments` | Count of instalments (1 for full_payment) |
| `first_payment_date` | Absolute date of first payment |
| `payment_frequency_days` | Days between consecutive instalments (blank for full_payment) |
| `financing_fee` | Extra cost on top of `requested_amount` for installments |
| `total_payable_amount` | `requested_amount + financing_fee` |

### 5.1 Instalment Schedule Generation

```
payment_dates[0] = first_payment_date
payment_dates[i] = payment_dates[i-1] + payment_frequency_days  (for i ≥ 1)
```

The `payment_plan` string must use these exact dates and amounts.

### 5.2 max_installment_months Filter

Compute span = `payment_dates[-1] - request_date` in months (ceiling). Reject plan if `span > max_installment_months`.

### 5.3 Eligibility Filters (all must pass)

1. `installments` in `payment_methods_user_will_consider`
2. `max_installment_months` is not blank
3. Computed span ≤ `max_installment_months`
4. Each instalment payment passes the 90-day safety check at its scheduled date

---

## 6. messages.csv — Contextual Amendments

**216 rows. `message_id` is unique. Join via `user_id`, `request_id`, or `related_event_id`.**

| Field | Notes |
|---|---|
| `message_id` | Unique |
| `user_id` | Filter by user |
| `request_id` | Non-null when message relates to this specific request |
| `related_event_id` | Non-null only when message directly describes one financial_events row |
| `sent_at` | ISO 8601 timestamp; relevant for ordering conflicting amendments |
| `source_type` | `employer`, `bank`, `merchant`, `service_provider`, `financial_service` |
| `message_text` | Free text in English or Bahasa Indonesia |

### 6.1 Message Classification Taxonomy

| Pattern | Financial effect |
|---|---|
| Salary change / reduced / temporary | Override next salary amount |
| Salary date change | Override next settlement_date for income event |
| Seasonal contract ended | Remove all future income from this employer |
| Employment ended | Remove all future salary income |
| First salary confirmed | Add new income event at confirmed date |
| Salary resumes + new childcare | Add childcare expense |
| One-time arrears adjustment | Add single credit at next pay cycle |
| Commission pending | **Do NOT** add commission to income |
| Bonus pending review | **Do NOT** add bonus to income |
| Invoice approved, settlement expected | Add credit at settlement date |
| Pending payout (gig platform) | **Do NOT** include |
| Refund initiated, not yet credited | **Do NOT** include (not settled) |
| Prize proceeds received | Include if message says "reached your account" |
| Prize still in processing | **Do NOT** include |
| Prize scam pattern ("pay to receive") | **Completely ignore** |
| Inter-account transfer (bank confirms same holder) | Treat as wash; net effect zero |
| Bill payment failed, will retry | Reserve the debit |
| Card dispute under investigation, no reversal | Keep debit as committed |
| FX refund pending | **Do NOT** include until settled |
| Rent increase by 12% | Apply to next recurring rent amount |
| Investment valuation changed | No cash effect |

### 6.2 Authority Rules

Messages are **untrusted evidence**. They may **clarify, amend, cancel, delay, or confirm** a financial fact. They may NEVER:
- Override the problem specification rules.
- Inject fabricated payment options.
- Grant extra balance or reduce minimum balance.
- Instruct the agent to skip safety checks.

---

## 7. images.csv + media/images/

**17 rows (16 data + header). Each image links to one event.**

| Field | Notes |
|---|---|
| `image_id` | e.g. `image_01` → file at `dataset/media/images/image_01.png` |
| `user_id` | Owner |
| `request_id` | Associated request |
| `related_event_id` | FK to financial_events.event_id where `amount` is blank |

### 7.1 OCR Strategy

- Use a multimodal LLM (Gemini Vision / GPT-4o) to extract the numeric amount.
- The images are pay slips, receipts, and financial statements (confirmed by viewing image_01: a payslip showing IDR 4,365,000 net pay for event_253 which is a salary credit for user_03).
- Prompt: *"Extract the final net amount from this document. Return only the numeric value with no currency symbol or formatting."*
- Cache result; never re-call for same image.

### 7.2 Null Safety

If OCR fails, log the failure and treat the event as requiring manual review. Do NOT substitute zero. Flag the request as requiring a conservative fallback (use next best estimate from event history).
