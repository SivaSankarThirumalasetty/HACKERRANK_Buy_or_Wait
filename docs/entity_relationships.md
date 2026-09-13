# Entity Relationships

All relationships derived from direct dataset inspection. No assumptions made.

---

## Entity-Relationship Diagram

```
financial_profiles (1)
    ├── user_id ──────────────────────┐
    │                                 │
    ▼                                 ▼
financial_events (N)              requests (N)
    ├── event_id                      ├── request_id
    ├── user_id (FK)                  ├── user_id (FK)
    ├── linked_event_id (self-FK)     │
    │                                 ▼
    ├── event_id ──────────────── images (N)
    │                 (via           ├── image_id
    │            related_event_id)   ├── user_id (FK)
    │                                ├── request_id (FK)
    │                                └── related_event_id (FK)
    │
messages (N)
    ├── message_id
    ├── user_id (FK)
    ├── request_id (FK, optional)
    └── related_event_id (FK, optional)

requests (1)
    └── request_id ────────────── request_payment_options (N)
                                      ├── payment_option_id
                                      └── request_id (FK)

financial_events (N)
    └── currency + settlement_date ── exchange_rates (N)
                                          ├── rate_date
                                          ├── from_currency
                                          └── to_currency
```

---

## Cardinalities

| Relationship | From | To | Cardinality |
|---|---|---|---|
| Profile → Events | `user_id` | `user_id` | 1 : N (avg ~92 events/user) |
| Profile → Requests | `user_id` | `user_id` | 1 : 1 (each request has unique user in eval set) |
| Profile → Messages | `user_id` | `user_id` | 0 : N |
| Profile → Images | `user_id` | `user_id` | 0 : 1 |
| Request → Payment Options | `request_id` | `request_id` | 1 : 2..4 |
| Request → Messages | `request_id` | `request_id` | 0 : N |
| Request → Images | `request_id` | `request_id` | 0 : 1 |
| Event → Images | `event_id` | `related_event_id` | 0 : 1 |
| Event → Messages | `event_id` | `related_event_id` | 0 : N |
| Event → Event (self) | `event_id` | `linked_event_id` | 0 : 1 |
| Event → Exchange Rate | `(currency, settlement_date)` | `(from_currency, rate_date)` | N : 1 |

---

## Detailed Relationship Specifications

### 1. financial_profiles → financial_events

**Join key:** `user_id`
**Cardinality:** 1 (profile) : N (events)
**Coverage:** All 275 users have ≥1 event (confirmed by audit)
**Average events per user:** ~92
**Use:** Get all events for a request's user_id before building cashflow model

```python
user_events = [e for e in events if e['user_id'] == request['user_id']]
```

---

### 2. financial_profiles → requests

**Join key:** `user_id`
**Cardinality in eval set:** 1 : 1 (each of the 250 eval requests has a different user_id)
**Coverage:** 100% — all 250 request users exist in profiles
**Use:** Load user's preferences, balance, minimum, and payment methods

```python
profile = profiles_by_user[request['user_id']]
```

---

### 3. requests → request_payment_options

**Join key:** `request_id`
**Cardinality:** 1 : 2..4 (always at least 2, at most 4 options per request)
**Coverage:** All 275 requests (sample + eval) have options; no gaps
**Important:** The 25 sample requests also have payment options in this file (request_01–request_25)

```python
options = pay_opts_by_request[request['request_id']]
```

---

### 4. financial_events → images (via related_event_id)

**Join key:** `event_id` ↔ `related_event_id`
**Cardinality:** 0..1 : 1 (at most one image per event; exactly 16 events have images)
**Usage:** When `event.amount == ""`, look up `images_by_event[event_id]` to get `image_id`

```python
if not event['amount']:
    img = images_by_event.get(event['event_id'])
    if img:
        amount = ocr_extract(f"dataset/media/images/{img['image_id']}.png")
```

---

### 5. financial_events → messages (via related_event_id)

**Join key:** `event_id` ↔ `related_event_id`
**Cardinality:** 0 : N (an event can have 0 or more messages referencing it)
**Coverage:** 39 messages have `related_event_id` set; all reference valid events

**Messages by event type:**

| event_id | User | Event Type | Messages |
|---|---|---|---|
| event_1785 | user_20 | refund/pending | message_14 — refund initiated, not credited |
| event_1960 | user_22 | investment_valuation | message_15 — portfolio value increased, no cash |
| event_2165 | user_24 | windfall/income | message_17 — prize proceeds received |
| event_3230 | user_35 | refund/pending | message_25 — refund initiated, not credited |
| event_3491 | user_38 | windfall/income | message_28 — prize proceeds received |
| event_4535 | user_48 | expense/settled | message_35 — receipt confirmation |
| event_4994 | user_53 | refund/pending | message_39 — refund initiated, not credited |
| event_6532 | user_70 | investment_valuation | message_52 — portfolio value increased, no cash |
| event_6859 | user_73 | expense/scheduled | (image_11 only) |
| event_7186 | user_77 | refund/pending | message_59 — refund initiated, not credited |
| event_7941 | user_84 | expense/settled | message_64 — receipt confirmation |
| event_8575 | user_91 | debt_payment/failed | message_69 — failed debit, will retry |
| event_9420 | user_101 | windfall/income | message_75 — prize proceeds received |
| event_9805 | user_105 | investment_valuation | message_79 — portfolio value increased, no cash |
| event_10521 | user_113 | expense/settled | message_86 — EV charging receipt + salary confirmation |
| event_10699 | user_115 | windfall/income | message_88 — prize proceeds received |
| event_11129 | user_120 | investment_sale | message_92 — investment sale proceeds settled |
| event_12709 | user_138 | expense/settled | message_106 — card charge under investigation |
| event_13032 | user_141 | investment_sale | message_108 — investment sale proceeds settled |
| event_13207 | user_143 | windfall/income | message_110 — prize proceeds received |
| event_13663 | user_148 | investment_sale | message_114 — investment sale proceeds settled |
| event_14026 | user_152 | work_expense/income | message_117 — work expense reimbursement |
| event_14399 | user_156 | expense | message_121 — card charge under investigation |
| event_17401 | user_188 | work_expense/income | message_150 — work expense reimbursement |
| event_17662 | user_191 | refund/pending | message_152 — refund initiated, not credited |
| event_18269 | user_198 | expense | message_157 — card charge under investigation |
| event_19182 | user_208 | investment_valuation | message_163 — investment value down, no cash |
| event_19334 | user_210 | expense | message_164 — card charge under investigation |
| event_20379 | user_221 | refund/pending | message_172 — refund initiated, not credited |
| event_20615 | user_224 | work_expense/income | message_174 — work expense reimbursement |
| event_21101 | user_229 | debt_payment/failed | message_179 — failed debit, will retry |
| event_21582 | user_234 | expense | message_183 — card charge under investigation |
| event_21785 | user_236 | investment_valuation | message_185 — investment value down, no cash |
| event_23203 | user_252 | expense | message_197 — card charge under investigation |
| event_23306 | user_253 | debt_payment/failed | message_198 — failed debit, will retry |
| event_23855 | user_259 | debt_payment/failed | message_201 — failed debit, will retry |
| event_24352 | user_264 | investment_valuation | message_205 — investment value down, no cash |
| event_24534 | user_266 | investment_valuation | message_207 — investment value up, no cash |
| event_25342 | user_275 | refund/pending | message_215 — refund initiated, not credited |

---

### 6. requests → messages (via request_id)

**Join key:** `request_id`
**Cardinality:** 0 : N
**Coverage:** 128 messages have `request_id` set (some sample, most evaluation requests)
**Use:** Load all messages for this request to apply financial amendments

```python
request_messages = msgs_by_request.get(request['request_id'], [])
user_messages = msgs_by_user.get(request['user_id'], [])
all_relevant_messages = set(request_messages + user_messages)
```

---

### 7. financial_events → exchange_rates

**Join key:** `(currency, settlement_date)` ↔ `(from_currency, rate_date)`
**Cardinality:** N : 1 (many events may share the same rate)
**Resolution:** Use the most recent rate_date on or before the event's settlement_date

**Applicable only when:** `event.currency != user.home_currency`

```python
def get_rate(from_cur, to_cur, as_of_date):
    candidates = [r for r in rates 
                  if r['from_currency'] == from_cur 
                  and r['to_currency'] == to_cur 
                  and parse_date(r['rate_date']) <= as_of_date]
    if not candidates:
        return None  # try multi-hop
    return max(candidates, key=lambda r: parse_date(r['rate_date']))['rate']
```

---

### 8. financial_events → financial_events (self-join via linked_event_id)

**Join key:** `linked_event_id` ↔ `event_id`
**Cardinality:** 0..1 : 1 (each event links to at most one parent)
**Coverage:** 58 events have a non-null `linked_event_id`; 0 orphan links

**Lifecycle patterns:**

| Pattern | Parent Status | Child Status | Resolution |
|---|---|---|---|
| Authorization → Settlement | `cancelled` | `settled` | Include only the settled child |
| Charge → Refund | `settled` (debit) | `settled` or `pending` (credit) | Include settled refund; exclude pending refund |
| Investment Purchase → Valuation | `settled` (debit) | `unrealized` (non_cash) | Include purchase; ALWAYS exclude valuation |
| Investment Purchase → Sale | `settled` (debit) | `settled` (credit) | Include both: purchase as debit, sale as credit |
| Debt → Revised Debt | `settled` | `settled` | Include both unless message indicates override |

---

## Key Lookup Patterns for Implementation

```python
# Build all indexes at startup
profiles_by_user = {r['user_id']: r for r in profiles}
events_by_id = {e['event_id']: e for e in events}
events_by_user = defaultdict(list)
for e in events:
    events_by_user[e['user_id']].append(e)

pay_opts_by_request = defaultdict(list)
for p in pay_opts:
    pay_opts_by_request[p['request_id']].append(p)

msgs_by_user = defaultdict(list)
msgs_by_request = defaultdict(list)
for m in messages:
    msgs_by_user[m['user_id']].append(m)
    if m['request_id']:
        msgs_by_request[m['request_id']].append(m)

images_by_event = {i['related_event_id']: i for i in images}
```

---

## Data Volume Summary

| Entity | Count | Size |
|---|---|---|
| Users (profiles) | 275 | 38 KB |
| Evaluation requests | 250 | Small |
| Sample requests | 25 | Small |
| Financial events | 25,342 | ~2.9 MB |
| Payment options | 790 | 63 KB |
| Messages | 215 | 68 KB |
| Images | 16 | 111 KB – 756 KB each |
| Exchange rates | 134 | Small |
