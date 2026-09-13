from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple, Dict
from src.models.domain import PaymentPlan, PaymentOption, FinancialProfile, ForecastDay, Request, FinancialEvent
from src.models.spending_change import SpendingChange
from src.forecasting.cashflow import build_cashflow_forecast
from src.currency.converter import ExchangeRateTable
from src.explainability.trace import CandidatePlanEvaluation, DecisionTrace
import re

def check_schedule_safety(
    schedule: List[Tuple[date, Decimal]],
    forecast: List[ForecastDay],
    minimum_balance: Decimal
) -> Tuple[bool, Optional[date], Optional[Decimal], Optional[Decimal]]:
    """
    Evaluates safety of a chronological payment schedule.
    Returns: (is_safe, violation_date, projected_balance, deficit)
    """
    daily_plan_debits = {}
    for p_date, p_amt in schedule:
        daily_plan_debits[p_date] = daily_plan_debits.get(p_date, Decimal('0')) + p_amt

    cum_plan_debit = Decimal('0')
    for f in forecast:
        if f.day in daily_plan_debits:
            cum_plan_debit += daily_plan_debits[f.day]
        projected = f.closing_balance - cum_plan_debit
        if projected < minimum_balance:
            deficit = minimum_balance - projected
            return False, f.day, projected, deficit
    return True, None, None, None

def is_schedule_safe(schedule: List[Tuple[date, Decimal]], forecast: List[ForecastDay], minimum_balance: Decimal) -> bool:
    safe, _, _, _ = check_schedule_safety(schedule, forecast, minimum_balance)
    return safe

def generate_full_payment_plan(
    option: PaymentOption,
    profile: FinancialProfile,
    forecast: List[ForecastDay],
    spending_changes: Optional[List[SpendingChange]] = None,
    total_spending_reduction: Decimal = Decimal('0')
) -> PaymentPlan:
    schedule = [(option.first_payment_date, option.payment_amount)]
    safe = is_schedule_safe(schedule, forecast, profile.minimum_balance_to_keep)
    return PaymentPlan(
        plan_type='full_payment',
        payments=schedule,
        total_amount=option.payment_amount,
        financing_fee=option.financing_fee,
        option_id=option.payment_option_id,
        is_safe=safe,
        explanation=f"Pay {profile.home_currency} {option.payment_amount} in full on {option.first_payment_date}",
        spending_changes=spending_changes or [],
        completion_date=option.first_payment_date,
        total_spending_reduction=total_spending_reduction
    )

def generate_partial_payment_plan(
    request: Request,
    profile: FinancialProfile,
    amount_safe_now: Decimal,
    earliest_full_date: Optional[date],
    forecast: List[ForecastDay],
    spending_changes: Optional[List[SpendingChange]] = None
) -> Optional[PaymentPlan]:
    """
    Partial payment plan:
    - request must allow partial payment
    - user must accept partial_payment
    - 0 < amount_safe_to_pay < requested_amount
    - earliest_full_date <= desired_completion_date
    - exactly two payments: amount_safe_to_pay on request_date, remainder on earliest_full_date
    - total equals requested_amount
    """
    if not request.allows_partial_payment:
        return None
    if 'partial_payment' not in profile.payment_methods:
        return None
    if amount_safe_now <= 0 or amount_safe_now >= request.requested_amount:
        return None
    if not earliest_full_date:
        return None
    if earliest_full_date > request.desired_completion_date:
        return None

    remainder = request.requested_amount - amount_safe_now
    schedule = [(request.request_date, amount_safe_now), (earliest_full_date, remainder)]
    safe = is_schedule_safe(schedule, forecast, profile.minimum_balance_to_keep)
    if not safe:
        return None

    return PaymentPlan(
        plan_type='partial_payment',
        payments=schedule,
        total_amount=request.requested_amount,
        financing_fee=Decimal('0'),
        option_id=None,
        is_safe=True,
        explanation=f"Pay {profile.home_currency} {amount_safe_now} today and remaining {remainder} on {earliest_full_date}",
        spending_changes=spending_changes or [],
        completion_date=earliest_full_date
    )

def generate_installment_plan(
    option: PaymentOption,
    profile: FinancialProfile,
    forecast: List[ForecastDay],
    spending_changes: Optional[List[SpendingChange]] = None,
    total_spending_reduction: Decimal = Decimal('0')
) -> Optional[PaymentPlan]:
    """
    Installment plan following supplied payment option.
    Rejects if user does not consider installments or exceeded max_installment_months.
    """
    if 'installments' not in profile.payment_methods:
        return None
    if profile.max_installment_months is None:
        return None
    if option.number_of_payments > profile.max_installment_months:
        return None

    payments = []
    curr_date = option.first_payment_date
    for _ in range(option.number_of_payments):
        payments.append((curr_date, option.payment_amount))
        if option.payment_frequency_days:
            curr_date += timedelta(days=option.payment_frequency_days)
        else:
            curr_date += timedelta(days=30)

    completion_date = payments[-1][0]
    safe = is_schedule_safe(payments, forecast, profile.minimum_balance_to_keep)
    if not safe:
        return None

    return PaymentPlan(
        plan_type='installments',
        payments=payments,
        total_amount=option.total_payable_amount,
        financing_fee=option.financing_fee,
        option_id=option.payment_option_id,
        is_safe=True,
        explanation=f"Use {option.number_of_payments} installments of {profile.home_currency} {option.payment_amount}",
        spending_changes=spending_changes or [],
        completion_date=completion_date,
        total_spending_reduction=total_spending_reduction
    )

def generate_wait_plan(
    request: Request,
    profile: FinancialProfile,
    earliest_full_date: Optional[date],
    forecast: List[ForecastDay]
) -> Optional[PaymentPlan]:
    """
    Wait plan:
    - full payment becomes safe later (earliest_full_date > request_date)
    - user accepts full_payment
    """
    if 'full_payment' not in profile.payment_methods:
        return None
    if not earliest_full_date or earliest_full_date <= request.request_date:
        return None

    schedule = [(earliest_full_date, request.requested_amount)]
    safe = is_schedule_safe(schedule, forecast, profile.minimum_balance_to_keep)
    if not safe:
        return None

    return PaymentPlan(
        plan_type='wait',
        payments=schedule,
        total_amount=request.requested_amount,
        financing_fee=Decimal('0'),
        option_id=None,
        is_safe=True,
        explanation=f"Wait until {earliest_full_date}, then pay {profile.home_currency} {request.requested_amount} in full",
        spending_changes=[],
        completion_date=earliest_full_date
    )

def rank_candidate_plans(
    candidates: List[PaymentPlan],
    request: Request,
    trace: Optional[DecisionTrace] = None
) -> Optional[PaymentPlan]:
    """
    Ranks safe candidate plans according to exact specification priority:
    1. Complete the request by desired_completion_date (True before False)
    2. Require no spending changes (len == 0 before len > 0)
    3. Minimize total amount paid (lowest total_amount)
    4. Start payment earlier (earliest first_payment_date)
    5. Use fewer payments (lowest count)
    6. Lowest payment_option_id numeric value (tie-breaker)
    """
    if not candidates:
        if trace:
            trace.selection_rationale = "No candidate plans available"
        return None

    def get_option_num(opt_id: Optional[str]) -> int:
        if not opt_id:
            return 999999
        digits = re.findall(r'\d+', opt_id)
        return int(digits[0]) if digits else 999999

    safe_candidates = [p for p in candidates if p.is_safe]
    if not safe_candidates:
        if trace:
            trace.selection_rationale = "No safe plans survived validation"
            for p in candidates:
                first_d = p.payments[0][0] if p.payments else date.max
                last_d = p.completion_date or (p.payments[-1][0] if p.payments else date.max)
                eval_item = CandidatePlanEvaluation(
                    plan=p,
                    plan_type=p.plan_type,
                    option_id=p.option_id,
                    completion_date=last_d,
                    completes_on_time=(last_d <= request.desired_completion_date),
                    requires_spending_changes=(len(p.spending_changes) > 0),
                    total_amount_paid=p.total_amount,
                    first_payment_date=first_d,
                    number_of_payments=len(p.payments),
                    option_id_numeric=get_option_num(p.option_id),
                    is_safe=p.is_safe,
                    rejection_reason=None if p.is_safe else "Insufficient balance or margin violation"
                )
                trace.add_evaluation(eval_item)
        return None

    def sort_key(p: PaymentPlan):
        first_date = p.payments[0][0] if p.payments else date.max
        last_date = p.completion_date or (p.payments[-1][0] if p.payments else date.max)
        on_time = (last_date <= request.desired_completion_date)
        no_changes = (len(p.spending_changes) == 0)
        spending_reduction = p.total_spending_reduction
        total_paid = p.total_amount
        num_payments = len(p.payments)
        opt_num = get_option_num(p.option_id)

        # 1. on_time (True -> 0, False -> 1)
        # 2. no_changes (True -> 0, False -> 1)
        # 3. total_paid (Decimal ascending)
        # 4. first_date (date ascending)
        # 5. num_payments (int ascending)
        # 6. opt_num (int ascending)
        return (
            0 if on_time else 1,
            0 if no_changes else 1,
            total_paid,
            first_date,
            num_payments,
            opt_num
        )

    safe_candidates.sort(key=sort_key)
    selected = safe_candidates[0]

    if trace:
        for p in candidates:
            first_d = p.payments[0][0] if p.payments else date.max
            last_d = p.completion_date or (p.payments[-1][0] if p.payments else date.max)
            eval_item = CandidatePlanEvaluation(
                plan=p,
                plan_type=p.plan_type,
                option_id=p.option_id,
                completion_date=last_d,
                completes_on_time=(last_d <= request.desired_completion_date),
                requires_spending_changes=(len(p.spending_changes) > 0),
                total_amount_paid=p.total_amount,
                first_payment_date=first_d,
                number_of_payments=len(p.payments),
                option_id_numeric=get_option_num(p.option_id),
                is_safe=p.is_safe,
                rejection_reason=None if p.is_safe else "Insufficient balance or margin violation"
            )
            trace.add_evaluation(eval_item)
        trace.selected_plan = selected
        trace.selection_rationale = f"Ranked highest among {len(safe_candidates)} safe candidate plans"

    return selected

def format_amount(amt: Decimal) -> str:
    s = f"{amt:f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

def format_payment_plan(plan: Optional[PaymentPlan]) -> str:
    if not plan or not plan.payments or plan.plan_type == 'not_recommended':
        return 'none'
    return '|'.join([f"{p[0].strftime('%Y-%m-%d')}:{format_amount(p[1])}" for p in plan.payments])

def format_spending_changes(changes: Optional[List[SpendingChange]]) -> str:
    if not changes:
        return 'none'
    return '|'.join([c.to_str() for c in changes])
