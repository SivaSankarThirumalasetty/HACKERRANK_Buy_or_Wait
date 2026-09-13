from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional
from src.models.domain import FinancialEvent

@dataclass
class RecurringStream:
    stream_id: str
    user_id: str
    category: str
    event_type: str
    direction: str
    currency: str
    cadence: str  # 'weekly', 'biweekly', 'monthly_calendar', 'fixed_days', 'irregular'
    period_days: int
    amount_rule: str  # 'exact', 'last_known', 'amended'
    base_amount: Decimal
    day_of_month: Optional[int] = None
    is_month_end: bool = False
    historical_evidence: List[FinancialEvent] = field(default_factory=list)
    scheduled_overrides: List[FinancialEvent] = field(default_factory=list)
    cancellation_date: Optional[date] = None
    projected_occurrences: List[FinancialEvent] = field(default_factory=list)
