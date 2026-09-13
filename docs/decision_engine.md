# Decision Engine

The decision engine is fully deterministic for financial calculations. An LLM is used only for image OCR and (optionally) for natural-language explanation generation.

---

## Step 0 — Preprocessing (Run Once at Startup)

### 0.1 Load All CSVs

```python
profiles     = load_csv('financial_profiles.csv', key='user_id')
events_by_u  = load_csv_grouped('financial_events.csv', key='user_id')
exchange_rates = load_csv('exchange_rates.csv')
pay_opts_by_r  = load_csv_grouped('request_payment_options.csv', key='request_id')
msgs_by_u    = load_csv_grouped('messages.csv', key='user_id')
images_by_ev = load_csv('images.csv', key='related_event_id')
requests     = load_csv('requests.csv')
```

### 0.2 OCR Blank Amounts (16 calls)

For every event where `amount == ""`:
1. Look up `images_by_ev[event_id]` → get `image_id`.
2. Load `dataset/media/images/{image_id}.png`.
3. Call multimodal LLM: extract numeric amount.
4. Store back as `event.amount = Decimal(ocr_result)`.

### 0.3 Global Currency Normaliser

Build a function `convert(amount, from_currency, to_currency, date)`:
- Exact match: find `(date_on_or_before(date), from_currency, to_currency)` in exchange_rates.
- If no direct rate: try multi-hop via USD as intermediary.
- Raise if no path found (should not happen for dataset currencies).

---

## Step 1 — Build User Context

For each request, build a `UserContext` object:

```
UserContext:
  profile          → from financial_profiles
  raw_events       → all events for this user_id
  messages         → all messages for this user_id
  payment_options  → all options for this request_id
  request          → current request row
```

---

## Step 2 — Event Lifecycle Resolution

Apply in this order (higher = wins):

1. **Explicit cancellation/settlement/amendment** (check `status` + `linked_event_id`)
2. **Newer record from same source** (compare `event_date`)
3. **Settled over estimated** (prefer `settled` over `pending` for same fact)
4. **Financially safer interpretation**

### 2.1 Event Inclusion Filter

```python
def is_cash_relevant(event):
    if event.direction == 'non_cash':      return False
    if event.status == 'cancelled':         return False
    if event.status == 'failed':            return False
    if event.status == 'unrealized':        return False
    if event.event_type == 'investment_valuation': return False
    # Credits only if settled or scheduled
    if event.direction == 'credit':
        return event.status in {'settled', 'scheduled'}
    # Debits if settled, pending, or scheduled
    if event.direction == 'debit':
        return event.status in {'settled', 'pending', 'scheduled'}
    return False
```

### 2.2 Deduplication

If two events have the same `user_id`, `event_type`, `category`, `amount`, and within 1 day of each other: keep the one with higher status priority (`settled > scheduled > pending`). Log the discarded event.

### 2.3 Pending Debit Reservation

Pending debits are **immediately reserved** from the starting balance — they represent committed outflows even if not yet settled.

---

## Step 3 — Message Amendments

Process messages for the current user, sorted by `sent_at` ascending (newest wins for same topic).

### 3.1 Salary Amendments

| Message Pattern | Action |
|---|---|
| "salary increased to X" | Set next scheduled income amount = X |
| "salary reduced to X" | Set next scheduled income amount = X (one cycle) |
| "temporary pay = X" | Set next scheduled income amount = X (one cycle) |
| "first salary = X confirmed for YYYY-MM-DD" | Add new income event at that date |
| "salary resumes on YYYY-MM-DD" | Ensure income event exists at that date |
| "employment ended / seasonal contract ended" | Remove all future salary events |
| "salary now expected on YYYY-MM-DD" | Shift next income settlement_date |
| "confirmed base salary = X; commission pending" | Use X only; exclude commission |
| "one-time arrears adjustment = X" | Add single credit on next pay date |
| "regular salary + childcare starts" | Add recurring childcare debit from that month |

### 3.2 Refund / Prize Messages

| Pattern | Action |
|---|---|
| "refund initiated, not yet credited" | Do NOT include refund event in cash |
| "prize proceeds reached your account" | Include the settled prize event |
| "prize still in processing" | Do NOT include |
| "pay release charge to receive prize" | **Scam — completely ignore** |
| "FX refund still processing" | Do NOT include |

### 3.3 Bank/Account Messages

| Pattern | Action |
|---|---|
| "inter-account transfer, same holder" | Net = 0; both debit and credit cancel out |
| "card charge under investigation, no reversal" | Keep debit as committed |
| "failed debit, will retry" | Reserve as pending debit |
| "minimum payments on two separate card accounts" | Both are independent debits |

### 3.4 Service Provider Messages

| Pattern | Action |
|---|---|
| "lease renewed, rent up 12%" | Multiply next recurring rent by 1.12 |
| "invoice approved, settlement on YYYY-MM-DD" | Add credit on that date if not already in events |
| "gig payout still pending" | Do NOT include |

---

## Step 4 — Recurrence Detection & Cashflow Model

### 4.1 Identify Recurring Series

A series is recurring when:
- ≥ 2 settled instances of same `(user_id, event_type, category)` in the 6 months before `request_date`
- Consistent interval (±5 days tolerance) between occurrences

For each recurring series, compute:
- **Median interval** (in days)
- **Median amount** (for variable-amount series like groceries)
- **Last occurrence date**
- **Next occurrence date** = last + interval

### 4.2 Build Daily Timeline

```
timeline = {}  # date → net_cash_flow

# Step A: Start with current_available_balance (already reflects pending debits reserved)
# Step B: Add all future settled/scheduled events in [request_date, request_date+90]
# Step C: Project recurring series forward:
#   next_date = last_occurrence + median_interval
#   while next_date <= request_date + 90:
#       timeline[next_date] += direction * median_amount
#       next_date += median_interval
```

### 4.3 Variable-Amount Recurring Expenses

For categories with natural variability (groceries, transport, dining, utilities):
- Use the **95th percentile** of the last 3 months of observed amounts as the forecast amount.
- This is the "conservative estimate" required by the spec.

---

## Step 5 — Amount Safe to Pay (Binary Search)

```python
def compute_amount_safe_to_pay(timeline, starting_balance, min_balance, requested_amount):
    """
    Find the maximum X in [0, requested_amount] such that:
    when X is debited on request_date, the running balance never
    drops below min_balance for any day in [request_date, request_date+90].
    """
    lo, hi = Decimal('0'), Decimal(requested_amount)
    
    while hi - lo > Decimal('0.01'):
        mid = (lo + hi) / 2
        if balance_ok(timeline, starting_balance - mid, min_balance):
            lo = mid
        else:
            hi = mid
    
    return round(lo, 2)  # round to 2 decimal places

def balance_ok(timeline, initial, min_balance):
    balance = initial
    for date in sorted(timeline.keys()):
        balance += timeline[date]
        if balance < min_balance:
            return False
    return True
```

**Note:** `amount_safe_to_pay` is computed BEFORE optional spending changes.

---

## Step 6 — Plan Generation

### 6.1 Full Payment

```
if 'full_payment' in user.payment_methods_user_will_consider:
    option = find(pay_opts, method='full_payment')  # always exists
    if balance_ok(sim with full_payment on first_payment_date):
        emit plan: full_payment on option.first_payment_date
```

### 6.2 Partial Payment

```
if 'partial_payment' in user.payment_methods_user_will_consider:
    if request.allows_partial_payment == 'true':
        if 0 < amount_safe_to_pay < requested_amount:
            remainder = requested_amount - amount_safe_to_pay
            # Find earliest date d >= request_date where remainder is safe
            earliest = find_earliest_safe_date(sim, remainder)
            if earliest <= desired_completion_date:
                emit plan: partial_payment
                    [request_date: amount_safe_to_pay,
                     earliest: remainder]
```

### 6.3 Installments

For each option with `payment_method == 'installments'`:
```
    # 1. Filter by user eligibility
    if 'installments' not in user.payment_methods_user_will_consider: skip
    if user.max_installment_months is blank: skip
    span_months = months(last_payment_date - request_date)
    if span_months > user.max_installment_months: skip
    
    # 2. Check all instalments pass safety check
    sim_copy = simulate with instalments injected
    if all instalments pass and last_payment <= desired_completion_date:
        emit plan: installments per this option schedule
```

### 6.4 Wait (Scan for Earliest Safe Full Payment)

```
earliest_full_date = None
for d in date_range(request_date, request_date + 90):
    if simulate(inject full payment on d) is safe:
        earliest_full_date = d
        break

if 'full_payment' in user.payment_methods_user_will_consider:
    if earliest_full_date and earliest_full_date <= desired_completion_date:
        emit plan: wait, then full_payment on earliest_full_date
```

### 6.5 Spending Changes (Try Combinations)

```
flexible_stops   = events where flexibility in {'stoppable', 'reducible_or_stoppable'}
                   and category in user.expense_categories_user_is_willing_to_stop
                   and NOT in user.expense_categories_to_protect

flexible_reduces = events where flexibility in {'reducible', 'reducible_or_stoppable'}
                   and category in user.expense_categories_user_is_willing_to_reduce
                   and NOT in user.expense_categories_to_protect

# Generate combinations of up to 3 changes (not mixing stop+reduce on same event)
for combo in combinations(flexible_stops, flexible_reduces, max=3):
    # Apply changes to simulation
    modified_sim = apply_changes(sim, combo)
    # Re-run plan generation on modified sim
    # Collect any new eligible plans
```

### 6.6 Fallback: not_recommended

If no safe plan found: emit `not_recommended`, `none` payment_plan, `not_affordable` status.

---

## Step 7 — Plan Ranking

When multiple eligible plans exist, rank by:

1. **Completes by `desired_completion_date`** (higher priority if True)
2. **No spending changes** (prefer no changes)
3. **Lowest `total_payable_amount`** (min cost)
4. **Earliest `first_payment_date`** (start sooner)
5. **Fewest payments** (`number_of_payments`)
6. **Lowest `payment_option_id`** (numeric tiebreaker)

---

## Step 8 — Affordability Status Mapping

| Condition | `affordability_status` | `recommended_payment_method` |
|---|---|---|
| Full payment safe on request_date | `affordable_now` | `full_payment` |
| Full amount completed via plan | `affordable_with_plan` | `full_payment` / `partial_payment` / `installments` |
| Full amount safe only on a future date | `affordable_later` | `wait` |
| Cannot complete safely | `not_affordable` | `not_recommended` |

**Special case:** `affordable_with_plan` + `full_payment` = full payment today is enabled by stopping/reducing a flexible expense.

---

## Step 9 — earliest_date_for_full_payment

- For `affordable_now`: equals `request_date`.
- For all others: earliest date d where simulating a single full payment on d passes the 90-day safety check.
- Empty string if no such date exists within 90 days.
- This field is computed **independently** of the user's payment_method preferences (e.g., if the user only considers installments, the field still reports the earliest date a full payment would theoretically be safe).

---

## Step 10 — spending_changes_needed

- `none` if no changes are required for the recommended plan.
- Up to 3 actions, pipe-separated.
- Format: `stop:<event_id>` or `reduce_to:<event_id>:<new_amount>`.
- `new_amount` must be ≥ `minimum_allowed_amount` for the event.
- `stop` and `reduce_to` must not reference the same `event_id`.
- Only recurring, flexible events in user-permitted categories may be referenced.

---

## Step 11 — payment_plan Serialisation

```
# For full_payment on date D at amount A:
plan_str = f"{D}:{A}"

# For installments with schedule [d1:a1, d2:a2, ...]:
plan_str = "|".join(f"{d}:{a}" for d, a in schedule)

# For partial_payment:
plan_str = f"{request_date}:{amount_safe_to_pay}|{earliest_date}:{remainder}"

# For wait:
plan_str = f"{earliest_date}:{requested_amount}"

# Not recommended:
plan_str = "none"
```

---

## Step 12 — Output Validation (Pre-write Assertions)

Before writing any row, assert:
1. `0 <= amount_safe_to_pay <= requested_amount`
2. `affordability_status` ∈ allowed enum
3. `recommended_payment_method` ∈ allowed enum AND in `payment_methods_user_will_consider` (or `not_recommended`)
4. For `affordable_now`: `earliest_date_for_full_payment == request_date`
5. For `not_affordable` / `not_recommended`: `payment_plan == 'none'` and `earliest_date_for_full_payment == ''`
6. For `partial_payment`: payments sum to `requested_amount`; exactly 2 payments
7. For `installments`: plan exactly matches a `request_payment_options` row
8. `spending_changes_needed` references only flexible recurring events
9. `stop` and `reduce_to` are not on the same `event_id`
10. At most 3 spending changes
