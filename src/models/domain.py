from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from typing import Optional

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: list[str]
    expense_categories_to_protect: list[str]
    expense_categories_to_reduce: list[str]
    expense_categories_to_stop: list[str]
    payment_methods: list[str]
    max_installment_months: Optional[int]

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_date: date
    settlement_date: date
    event_type: str
    description: str
    amount: Optional[Decimal]
    currency: str
    direction: str
    status: str
    flexibility: str
    category: str
    linked_event_id: Optional[str]
    is_recurring: bool = False
    recurrence_period_days: Optional[int] = None
    minimum_allowed_amount: Optional[Decimal] = None

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Decimal
    currency: str
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    number_of_payments: int
    payment_amount: Decimal
    payment_frequency_days: Optional[int]
    financing_fee: Decimal
    total_payable_amount: Decimal
    first_payment_date: date

@dataclass
class MessageEvidence:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: datetime
    source_type: str
    message_text: str
    effect_type: str = 'unknown'
    effect_data: dict = field(default_factory=dict)

@dataclass
class ImageEvidence:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: str
    extracted_amount: Decimal
    currency: str
    confidence: str

@dataclass
class ForecastDay:
    day: date
    opening_balance: Decimal
    credits: Decimal
    debits: Decimal
    closing_balance: Decimal
    events: list[str]

@dataclass
class PaymentPlan:
    plan_type: str
    payments: list[tuple[date, Decimal]]
    total_amount: Decimal
    financing_fee: Decimal
    option_id: Optional[str]
    is_safe: bool
    explanation: str
    spending_changes: list = field(default_factory=list)
    completion_date: Optional[date] = None
    total_spending_reduction: Decimal = Decimal('0')

@dataclass
class FinancialState:
    user_id: str
    as_of_date: date
    adjusted_balance: Decimal
    reserved_pending_debits: Decimal
    confirmed_income_upcoming: Decimal
    recurring_monthly_income: Decimal
    recurring_monthly_expenses: Decimal
    forecast: list[ForecastDay]

@dataclass  
class Decision:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: Optional[date]
    spending_changes_needed: str
    decision_explanation: str
