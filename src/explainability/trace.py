from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
import json
from src.models.domain import PaymentPlan, PaymentOption, FinancialProfile, Request

@dataclass
class SafetyCheckResult:
    is_safe: bool
    violation_date: Optional[date] = None
    projected_balance: Optional[Decimal] = None
    minimum_required: Optional[Decimal] = None
    deficit: Optional[Decimal] = None
    explanation: str = ""

@dataclass
class PlanEvaluation:
    plan_type: str
    option_id: Optional[str]
    is_safe: bool
    completes_on_time: bool
    requires_spending_changes: bool
    total_amount_paid: Decimal
    first_payment_date: date
    completion_date: date
    number_of_payments: int
    rejection_reason: Optional[str] = None
    safety_check: Optional[SafetyCheckResult] = None
    plan: Optional[PaymentPlan] = None
    option_id_numeric: int = 999999

# Alias for compatibility with payment_plans/generator.py
CandidatePlanEvaluation = PlanEvaluation

@dataclass
class DecisionTrace:
    request_id: str
    user_id: str
    request_date: Optional[date] = None
    requested_amount: Decimal = Decimal('0')
    currency: str = ""
    starting_balance: Decimal = Decimal('0')
    minimum_required_balance: Decimal = Decimal('0')
    protected_upcoming_expenses: Decimal = Decimal('0')
    expected_income_upcoming: Decimal = Decimal('0')
    user_payment_preferences: List[str] = field(default_factory=list)
    available_payment_options: List[Dict[str, Any]] = field(default_factory=list)
    relevant_evidence_summary: List[str] = field(default_factory=list)
    evaluated_plans: List[PlanEvaluation] = field(default_factory=list)
    selected_plan: Optional[Dict[str, Any]] = None
    earliest_safe_full_payment_date: Optional[date] = None
    spending_changes: List[str] = field(default_factory=list)
    concise_user_explanation: str = ""
    selection_rationale: str = ""

    def add_evaluation(self, eval_item: PlanEvaluation):
        self.evaluated_plans.append(eval_item)

    def to_dict(self) -> Dict[str, Any]:
        def serialize(obj):
            if isinstance(obj, (date, datetime)):
                return obj.strftime("%Y-%m-%d")
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        data = asdict(self)
        return json.loads(json.dumps(data, default=serialize))

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        lines = [
            f"Decision Trace for Request {self.request_id} (User: {self.user_id}):",
            f"  Requested: {self.currency} {self.requested_amount} on {self.request_date}",
            f"  Starting Balance: {self.currency} {self.starting_balance} (Minimum: {self.minimum_required_balance})",
            f"  Preferences: {', '.join(self.user_payment_preferences)}",
            f"  Candidate Plans Evaluated ({len(self.evaluated_plans)}):"
        ]
        for idx, ep in enumerate(self.evaluated_plans, 1):
            status = "SAFE" if ep.is_safe else f"REJECTED: {ep.rejection_reason}"
            lines.append(
                f"    [{idx}] {ep.plan_type} (opt: {ep.option_id}): {status} | "
                f"Total={ep.total_amount_paid} | Start={ep.first_payment_date} | Payments={ep.number_of_payments}"
            )
        if self.selected_plan:
            if isinstance(self.selected_plan, dict):
                p_type = self.selected_plan.get('plan_type')
                p_opt = self.selected_plan.get('option_id')
            else:
                p_type = getattr(self.selected_plan, 'plan_type', str(self.selected_plan))
                p_opt = getattr(self.selected_plan, 'option_id', None)
            lines.append(f"  Selected: {p_type} (Option: {p_opt}) - {self.selection_rationale}")
        else:
            lines.append(f"  Selected: None ({self.selection_rationale})")
        lines.append(f"  User Explanation: \"{self.concise_user_explanation}\"")
        return "\n".join(lines)
