from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional
from src.models.domain import PaymentPlan

@dataclass
class CandidatePlanEvaluation:
    plan: PaymentPlan
    completes_on_time: bool
    requires_spending_changes: bool
    total_amount_paid: Decimal
    first_payment_date: date
    number_of_payments: int
    option_id_numeric: int
    is_safe: bool
    rejection_reason: Optional[str] = None

@dataclass
class DecisionTrace:
    request_id: str
    user_id: str
    evaluated_plans: List[CandidatePlanEvaluation] = field(default_factory=list)
    selected_plan: Optional[PaymentPlan] = None
    selection_rationale: str = ""

    def add_evaluation(self, eval_item: CandidatePlanEvaluation):
        self.evaluated_plans.append(eval_item)

    def summary(self) -> str:
        lines = [f"Decision Trace for {self.request_id} (user {self.user_id}):"]
        for idx, ep in enumerate(self.evaluated_plans, 1):
            status_str = "SAFE" if ep.is_safe else f"REJECTED ({ep.rejection_reason})"
            lines.append(
                f"  [{idx}] {ep.plan.plan_type} (opt: {ep.plan.option_id}): {status_str} | "
                f"on_time={ep.completes_on_time} | no_changes={not ep.requires_spending_changes} | "
                f"total={ep.total_amount_paid} | start={ep.first_payment_date} | count={ep.number_of_payments}"
            )
        if self.selected_plan:
            lines.append(f"  --> Selected: {self.selected_plan.plan_type} ({self.selection_rationale})")
        else:
            lines.append(f"  --> Selected: None ({self.selection_rationale})")
        return "\n".join(lines)
