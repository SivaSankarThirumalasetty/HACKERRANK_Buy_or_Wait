from datetime import date
from decimal import Decimal
from typing import List, Optional
from src.models.domain import PaymentPlan, Request, FinancialProfile, ForecastDay
from src.models.spending_change import SpendingChange
from src.explainability.trace import SafetyCheckResult

def generate_concise_explanation(
    request: Request,
    profile: FinancialProfile,
    plan: Optional[PaymentPlan],
    earliest_full_date: Optional[date],
    safety_check: Optional[SafetyCheckResult] = None
) -> str:
    """
    Generates factual, grounded, concise financial explanations without internal chain-of-thought.
    Complies with official style guidelines:
    - Factual statements about amounts, dates, and minimum balance protection.
    - Explicit indication of first violation date when an option is rejected.
    """
    cur = profile.home_currency
    req_amt = request.requested_amount
    min_bal = profile.minimum_balance_to_keep

    if plan is None or plan.plan_type == 'not_recommended':
        if safety_check and not safety_check.is_safe and safety_check.violation_date:
            return (
                f"Not safe to pay the full amount today because the payment would reduce the projected balance "
                f"below the required {cur} {min_bal} minimum on {safety_check.violation_date}. "
                f"Do not make this payment by {request.desired_completion_date}."
            )
        return (
            f"Do not proceed with the {cur} {req_amt} request. None of the available options keeps the "
            f"{cur} {min_bal} minimum protected."
        )

    if plan.plan_type == 'full_payment':
        if plan.spending_changes:
            actions = []
            for sc in plan.spending_changes:
                if sc.action == 'stop':
                    actions.append(f"stop flexible expense {sc.event_id}")
                elif sc.action == 'reduce_to':
                    actions.append(f"reduce {sc.event_id} to {cur} {sc.new_amount}")
            changes_str = ", and ".join(actions)
            return (
                f"{changes_str.capitalize()}, then pay {cur} {req_amt} today. "
                f"This leaves the {cur} {min_bal} minimum protected."
            )
        return f"Pay {cur} {req_amt} today. This leaves the {cur} {min_bal} minimum protected over the next 90 days."

    if plan.plan_type == 'installments':
        num = len(plan.payments)
        first_amt = plan.payments[0][1]
        first_dt = plan.payments[0][0]
        return (
            f"Use {num} installments of {cur} {first_amt}, starting {first_dt}. "
            f"This keeps the {cur} {min_bal} minimum protected throughout the plan."
        )

    if plan.plan_type == 'partial_payment':
        first_amt = plan.payments[0][1]
        second_amt = plan.payments[1][1]
        second_dt = plan.payments[1][0]
        return (
            f"A two-step payment is safe: {cur} {first_amt} today and {cur} {second_amt} on {second_dt}. "
            f"This completes the full request and keeps the {cur} {min_bal} minimum protected."
        )

    if plan.plan_type == 'wait':
        return (
            f"Wait until {earliest_full_date}, then pay {cur} {req_amt} in full. "
            f"Paying earlier would take the balance below the {cur} {min_bal} minimum."
        )

    return f"Recommended payment method is {plan.plan_type}."
