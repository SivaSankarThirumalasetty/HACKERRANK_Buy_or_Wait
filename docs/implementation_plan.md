# Implementation Plan

## Goal

Implement the "Buy or Wait?" financial affordability agent that processes 250 evaluation requests and produces a valid `output.csv`.

## Timeline Overview (20h remaining)

| Phase | Duration | Description |
|---|---|---|
| Phase 1 | 1h | Project setup, skeleton, data loaders |
| Phase 2 | 2h | Event lifecycle resolution + message parser |
| Phase 3 | 1h | Currency normalisation |
| Phase 4 | 1h | Image OCR (16 images via LLM) |
| Phase 5 | 2h | Cashflow forecaster + 90-day simulator |
| Phase 6 | 2h | Decision engine (all plan types) |
| Phase 7 | 1h | Plan ranker + output serialiser |
| Phase 8 | 1h | Verifier + assertion layer |
| Phase 9 | 2h | LLM explanation generator |
| Phase 10 | 2h | Self-test on 25 samples + debugging |
| Phase 11 | 1h | Full 250-request run + usage_report.md |
| Phase 12 | 1h | Package code.zip + final submission prep |

---

## Proposed Project Tree

```
hackerrank-orchestrate-september26-main/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── problem_statement.md
├── log.txt                              # Chat transcript (gitignored)
├── output.csv                           # Generated predictions (repository root)
│
├── dataset/                             # Provided input files (DO NOT MODIFY)
│   ├── financial_profiles.csv
│   ├── financial_events.csv
│   ├── exchange_rates.csv
│   ├── request_payment_options.csv
│   ├── requests.csv
│   ├── sample_requests.csv
│   ├── messages.csv
│   ├── images.csv
│   ├── output.csv                       # Blank template
│   └── media/images/*.png              # 16 PNG images
│
├── code/                                # All solution code
│   ├── main.py                          # Entry point
│   ├── config.py                        # Constants, paths, model names
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py                    # CSV loading + indexing
│   │   ├── models.py                    # Dataclass definitions for all entities
│   │   └── validator.py                 # Input validation helpers
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── event_resolver.py            # Event lifecycle resolution
│   │   ├── message_parser.py            # Message classification + amendment
│   │   ├── currency_normaliser.py       # Exchange rate conversion
│   │   ├── image_ocr.py                 # LLM-based image OCR
│   │   └── recurrence_detector.py       # Recurring event detection
│   │
│   ├── finance/
│   │   ├── __init__.py
│   │   ├── forecaster.py                # 90-day timeline builder
│   │   ├── safe_pay_calculator.py       # Binary search for amount_safe_to_pay
│   │   └── spending_optimizer.py        # Flexible expense change generator
│   │
│   ├── planning/
│   │   ├── __init__.py
│   │   ├── plan_generator.py            # Generates all candidate plans
│   │   ├── plan_ranker.py               # Applies ranking rules
│   │   └── plan_verifier.py             # Re-validates chosen plan
│   │
│   ├── output/
│   │   ├── __init__.py
│   │   ├── explanation_generator.py     # LLM-based or template explanation
│   │   ├── serialiser.py                # Output row formatting
│   │   └── writer.py                    # CSV writer for output.csv
│   │
│   └── evaluation/
│       ├── __init__.py
│       ├── scorer.py                    # Self-scoring against sample_requests
│       └── usage_tracker.py             # Token/cost tracking
│
├── evaluation/
│   └── usage_report.md                  # Required by spec (auto-generated)
│
├── docs/
│   ├── architecture.md
│   ├── data_model.md
│   ├── decision_engine.md
│   ├── edge_cases.md
│   ├── evaluation_strategy.md
│   └── implementation_plan.md
│
├── .env.example                         # Template for API keys
├── requirements.txt                     # Python dependencies
└── .gitignore                           # Includes log.txt, .env, __pycache__
```

---

## Phase-by-Phase Implementation Details

### Phase 1: Project Setup

**Files:** `code/config.py`, `code/data/models.py`, `requirements.txt`, `.env.example`

```python
# code/data/models.py — Core dataclasses
@dataclass
class UserProfile:
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: list[str]
    expense_categories_to_protect: set[str]
    expense_categories_to_reduce: set[str]
    expense_categories_to_stop: set[str]
    payment_methods: list[str]
    max_installment_months: Optional[int]

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Optional[Decimal]  # None if blank
    currency: str
    event_date: date
    settlement_date: date
    status: str
    linked_event_id: Optional[str]
    flexibility: str
    minimum_allowed_amount: Optional[Decimal]

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: Decimal
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int]
    financing_fee: Decimal
    total_payable_amount: Decimal

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str
```

**Dependencies:** `pandas`, `Pillow`, `python-dotenv`, `google-generativeai` (or `openai`)

---

### Phase 2: Data Loaders

**File:** `code/data/loader.py`

```python
class DataLoader:
    def load_all(self) -> AllData:
        # Load all 9 CSVs
        # Build indexes: events by user_id, options by request_id, etc.
        # Return AllData container
```

**Key design:** Use `pandas` for the 25K-row events CSV; use `csv.DictReader` for smaller files.

---

### Phase 3: Event Lifecycle Resolution

**File:** `code/preprocessing/event_resolver.py`

```python
class EventResolver:
    def resolve(self, events: list[FinancialEvent]) -> list[FinancialEvent]:
        # 1. Filter: exclude non_cash, cancelled, failed, unrealized
        # 2. Filter: credits only if settled/scheduled
        # 3. Deduplicate: linked lifecycle events
        # 4. Flag: pending debits for reservation
```

---

### Phase 4: Message Parser

**File:** `code/preprocessing/message_parser.py`

```python
class MessageParser:
    PATTERNS = [
        (r'salary.*increased.*?([\d,]+)', 'salary_increase'),
        (r'temporary.*pay.*?([\d,]+)', 'salary_temp_reduction'),
        (r'seasonal contract.*ended|employment.*ended', 'income_ended'),
        (r'first salary.*?([\d,]+).*?(\d{4}-\d{2}-\d{2})', 'new_income'),
        (r'refund.*initiated.*not.*credited', 'refund_pending'),
        (r'prize.*reached.*account', 'prize_confirmed'),
        (r'pay.*release charge|pay.*processing charge', 'scam'),
        (r'lease.*increases.*12%', 'rent_increase_12pct'),
        (r'same account holder', 'inter_account_transfer'),
        # etc.
    ]
    
    def apply_amendments(self, context: UserContext) -> UserContext:
        # Classify messages, apply amendments to context
```

---

### Phase 5: Currency Normaliser

**File:** `code/preprocessing/currency_normaliser.py`

```python
class CurrencyNormaliser:
    def convert(self, amount: Decimal, from_cur: str, to_cur: str, 
                as_of_date: date) -> Decimal:
        # 1. Exact rate lookup
        # 2. Multi-hop via USD if needed
        # 3. Nearest-prior-date fallback
        # 4. Raise if no path found
```

---

### Phase 6: Image OCR

**File:** `code/preprocessing/image_ocr.py`

```python
class ImageOCR:
    def __init__(self, llm_client):
        self.cache = {}  # image_id -> Decimal amount
    
    def extract_amount(self, image_path: str, event_context: FinancialEvent) -> Decimal:
        if image_path in self.cache:
            return self.cache[image_path]
        # Load image, call LLM with structured prompt
        # Parse numeric result, cache, return
```

**Prompt template:**
```
Look at this financial document (pay slip, receipt, or bank statement).
Extract the final net/total amount that was transferred or paid.
Return ONLY the numeric value, no currency symbol, no formatting.
For example: 4365000
```

---

### Phase 7: Recurrence Detector

**File:** `code/preprocessing/recurrence_detector.py`

```python
class RecurrenceDetector:
    def detect(self, events: list[FinancialEvent], 
               request_date: date) -> list[RecurringPattern]:
        # Group by (user_id, category, event_type)
        # Check for >= 2 occurrences within 6 months of request_date
        # Compute median interval and forecast amount (95th pct for variable)
        # Return list of RecurringPattern objects
```

---

### Phase 8: 90-Day Forecaster

**File:** `code/finance/forecaster.py`

```python
class Forecaster:
    def build_timeline(self, context: UserContext, 
                       request_date: date) -> DailyTimeline:
        # 1. Start with current_available_balance
        # 2. Reserve pending debits
        # 3. Add settled/scheduled future events in [request_date, +90]
        # 4. Project recurring patterns forward
        # 5. Apply message amendments (salary changes, rent increases, etc.)
        # Return dict[date, net_cashflow]
    
    def simulate(self, timeline: DailyTimeline, initial_balance: Decimal,
                 injected_payments: list[Payment]) -> BalanceCurve:
        # Return day-by-day balance including injected payments
```

---

### Phase 9: Plan Generator + Ranker

**File:** `code/planning/plan_generator.py`

- Generates all 5 plan types (full, partial, installments, wait, spending_changes)
- Returns list of `CandidatePlan` objects

**File:** `code/planning/plan_ranker.py`

- Applies 6-level ranking from spec
- Returns `BestPlan`

---

### Phase 10: Verifier

**File:** `code/planning/plan_verifier.py`

```python
class PlanVerifier:
    def verify(self, plan: CandidatePlan, sim: BalanceCurve, 
               min_balance: Decimal) -> bool:
        # Re-simulate with plan injected
        # Check all assertions from evaluation_strategy.md §3
```

---

### Phase 11: Explanation Generator

**File:** `code/output/explanation_generator.py`

Two modes:
1. **LLM mode:** Pass structured facts to Gemini Flash; prompt: *"Generate a one-sentence financial decision explanation for: [facts]"*
2. **Template mode:** Fill: `"{action} {currency_amount} {details}. This {constraint phrase}."`

---

### Phase 12: Output Writer

**File:** `code/output/writer.py`

- Writes to root `output.csv` (not `dataset/output.csv`)
- Includes the exact column order required by spec

---

## Configuration (.env)

```
GOOGLE_API_KEY=<your_gemini_api_key>
# or
OPENAI_API_KEY=<your_openai_api_key>
MODEL_PROVIDER=gemini  # or openai
OCR_MODEL=gemini-1.5-flash
EXPLANATION_MODEL=gemini-1.5-flash
```

---

## requirements.txt

```
pandas>=2.0.0
google-generativeai>=0.7.0
python-dotenv>=1.0.0
Pillow>=10.0.0
```

---

## Run Instructions

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY=<your_key>

# 3. Run the solution
python code/main.py

# 4. Verify output
# output.csv will be created in the repository root
```

---

## code.zip Contents

```
code.zip/
├── code/
├── evaluation/
│   └── usage_report.md
├── docs/
├── dataset/                   # Input files (not images to keep size manageable)
├── .env.example
├── requirements.txt
├── README.md
└── output.csv
```

> **Note:** Do not include `.env`, `log.txt`, or any API keys in code.zip.
