from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict
from src.models.domain import FinancialProfile, ForecastDay, Request, FinancialEvent, PaymentOption, Decision, PaymentPlan
from src.models.spending_change import SpendingChange
from src.currency.converter import ExchangeRateTable
from src.forecasting.cashflow import build_cashflow_forecast, is_balance_safe_throughout
from src.evidence.messages import MessageAmendment
from src.payment_plans.generator import (
    generate_full_payment_plan,
    generate_partial_payment_plan,
    generate_installment_plan,
    generate_wait_plan,
    rank_candidate_plans,
    format_payment_plan,
    format_spending_changes
)
from src.affordability.spending_optimizer import (
    get_candidate_flexible_events,
    optimize_spending_for_schedule
)

def calculate_amount_safe_to_pay(
    profile: FinancialProfile,
    forecast: List[ForecastDay],
    request_date: date,
    requested_amount: Decimal
) -> Decimal:
    """
    Computes the maximum amount that can safely be paid on request_date
    before optional spending changes, keeping balance >= minimum_balance_to_keep
    throughout the forecast.
    """
    min_margin = requested_amount
    for f in forecast:
        if f.day >= request_date:
            margin = f.closing_balance - profile.minimum_balance_to_keep
            if margin < min_margin:
                min_margin = margin
    
    if min_margin < 0:
        return Decimal('0')
    
    best_safe = (min_margin * 100).quantize(Decimal('1'), rounding='ROUND_DOWN') / 100
    if best_safe > requested_amount:
        best_safe = requested_amount
    return best_safe

def find_earliest_safe_payment_date(
    profile: FinancialProfile,
    forecast: List[ForecastDay],
    requested_amount: Decimal,
    from_date: date,
    to_date: date
) -> Optional[date]:
    """
    Finds the first date in [from_date, to_date] where a single full payment
    of requested_amount can be made safely without spending changes.
    """
    for f in forecast:
        if from_date <= f.day <= to_date:
            safe = True
            for later_f in forecast:
                if later_f.day >= f.day:
                    if later_f.closing_balance - requested_amount < profile.minimum_balance_to_keep:
                        safe = False
                        break
            if safe:
                return f.day
    return None

from src.explainability.trace import DecisionTrace, PlanEvaluation, SafetyCheckResult
from src.explainability.generator import generate_concise_explanation
from src.payment_plans.generator import check_schedule_safety

def make_decision(
    request: Request,
    profile: FinancialProfile,
    events: List[FinancialEvent],
    payment_options: List[PaymentOption],
    fx_table: ExchangeRateTable,
    amendments: Optional[List[MessageAmendment]] = None
) -> Tuple[Decision, DecisionTrace]:
    """
    Top-level decision engine implementation following exact specification:
    1. Builds base 90-day forecast.
    2. Calculates amount_safe_to_pay and earliest_date_for_full_payment without spending changes.
    3. Evaluates all eligible candidate plans without spending changes.
    4. If no safe plan finishes on time, evaluates permitted spending changes.
    5. Applies specification ranking rules.
    6. Constructs structured Decision and comprehensive DecisionTrace.
    """
    forecast_end = request.request_date + timedelta(days=90)

    # Calculate expected income and protected expenses across forecast period
    expected_income = sum(
        ev.amount for ev in events
        if ev.direction == 'credit' and ev.status in ['settled', 'scheduled'] and ev.amount and request.request_date <= ev.settlement_date <= forecast_end
    )
    protected_expenses = sum(
        ev.amount for ev in events
        if ev.direction == 'debit' and ev.category in profile.expense_categories_to_protect and ev.amount and request.request_date <= ev.settlement_date <= forecast_end
    )

    trace = DecisionTrace(
        request_id=request.request_id,
        user_id=profile.user_id,
        request_date=request.request_date,
        requested_amount=request.requested_amount,
        currency=profile.home_currency,
        starting_balance=profile.current_available_balance,
        minimum_required_balance=profile.minimum_balance_to_keep,
        protected_upcoming_expenses=protected_expenses,
        expected_income_upcoming=expected_income,
        user_payment_preferences=profile.payment_methods,
        available_payment_options=[
            {
                "option_id": opt.payment_option_id,
                "method": opt.payment_method,
                "payments": opt.number_of_payments,
                "amount_per_payment": str(opt.payment_amount),
                "total": str(opt.total_payable_amount)
            }
            for opt in payment_options
        ],
        relevant_evidence_summary=[am.effect.value for am in amendments] if amendments else []
    )

    # 1. Base Forecast
    base_forecast = build_cashflow_forecast(
        profile=profile,
        events=events,
        request_date=request.request_date,
        fx_table=fx_table,
        amendments=amendments
    )

    # 2. Safety bounds without spending changes
    amount_safe_now = calculate_amount_safe_to_pay(profile, base_forecast, request.request_date, request.requested_amount)
    earliest_full_date = find_earliest_safe_payment_date(
        profile, base_forecast, request.requested_amount, request.request_date, forecast_end
    )

    candidate_plans: List[PaymentPlan] = []

    # 3. Generate candidate plans without spending changes
    # Full payment option
    full_opts = [opt for opt in payment_options if opt.payment_method == 'full_payment']
    for opt in full_opts:
        if 'full_payment' in profile.payment_methods:
            p_full = generate_full_payment_plan(opt, profile, base_forecast)
            candidate_plans.append(p_full)

    # Partial payment option
    if request.allows_partial_payment and 'partial_payment' in profile.payment_methods:
        p_part = generate_partial_payment_plan(request, profile, amount_safe_now, earliest_full_date, base_forecast)
        if p_part:
            candidate_plans.append(p_part)

    # Installment options
    inst_opts = [opt for opt in payment_options if opt.payment_method == 'installments']
    for opt in inst_opts:
        if 'installments' in profile.payment_methods:
            p_inst = generate_installment_plan(opt, profile, base_forecast)
            if p_inst:
                candidate_plans.append(p_inst)

    # Wait option
    if earliest_full_date and earliest_full_date > request.request_date:
        p_wait = generate_wait_plan(request, profile, earliest_full_date, base_forecast)
        if p_wait:
            candidate_plans.append(p_wait)

    best_plan = rank_candidate_plans(candidate_plans, request, trace)

    # 4. If no on-time safe plan without spending changes, explore deterministic spending changes
    need_spending_changes = (best_plan is None or (best_plan.completion_date and best_plan.completion_date > request.desired_completion_date))
    
    if need_spending_changes:
        candidate_events = get_candidate_flexible_events(profile, events, request.request_date)
        plans_with_changes: List[PaymentPlan] = []

        # Try full payment options with optimized spending changes
        if 'full_payment' in profile.payment_methods:
            for opt in full_opts:
                schedule = [(opt.first_payment_date, opt.payment_amount)]
                opt_res = optimize_spending_for_schedule(
                    payments=schedule,
                    profile=profile,
                    events=events,
                    request_date=request.request_date,
                    fx_table=fx_table,
                    amendments=amendments,
                    candidate_events=candidate_events
                )
                if opt_res is not None:
                    tot_red, changes = opt_res
                    mod_forecast = build_cashflow_forecast(
                        profile=profile,
                        events=events,
                        request_date=request.request_date,
                        fx_table=fx_table,
                        amendments=amendments,
                        spending_changes=changes
                    )
                    p_full = generate_full_payment_plan(
                        option=opt,
                        profile=profile,
                        forecast=mod_forecast,
                        spending_changes=changes,
                        total_spending_reduction=tot_red
                    )
                    if p_full.is_safe:
                        plans_with_changes.append(p_full)

        # Try installment options with optimized spending changes
        if 'installments' in profile.payment_methods:
            for opt in inst_opts:
                if profile.max_installment_months is not None and opt.number_of_payments <= profile.max_installment_months:
                    payments = []
                    curr_date = opt.first_payment_date
                    for _ in range(opt.number_of_payments):
                        payments.append((curr_date, opt.payment_amount))
                        if opt.payment_frequency_days:
                            curr_date += timedelta(days=opt.payment_frequency_days)
                        else:
                            curr_date += timedelta(days=30)

                    opt_res = optimize_spending_for_schedule(
                        payments=payments,
                        profile=profile,
                        events=events,
                        request_date=request.request_date,
                        fx_table=fx_table,
                        amendments=amendments,
                        candidate_events=candidate_events
                    )
                    if opt_res is not None:
                        tot_red, changes = opt_res
                        mod_forecast = build_cashflow_forecast(
                            profile=profile,
                            events=events,
                            request_date=request.request_date,
                            fx_table=fx_table,
                            amendments=amendments,
                            spending_changes=changes
                        )
                        p_inst = generate_installment_plan(
                            option=opt,
                            profile=profile,
                            forecast=mod_forecast,
                            spending_changes=changes,
                            total_spending_reduction=tot_red
                        )
                        if p_inst and p_inst.is_safe:
                            plans_with_changes.append(p_inst)

        if plans_with_changes:
            best_plan_with_change = rank_candidate_plans(plans_with_changes, request, trace)
            if best_plan_with_change:
                # If existing best_plan is None or doesn't finish on time, prefer change plan that finishes on time
                if best_plan is None or (best_plan_with_change.completion_date and best_plan_with_change.completion_date <= request.desired_completion_date):
                    best_plan = best_plan_with_change

    # 5. Determine Affordability Status & Recommended Payment Method
    if best_plan is None:
        affordability_status = 'not_affordable'
        recommended_payment_method = 'not_recommended'
        final_plan_str = 'none'
        spending_changes_str = 'none'
        explanation = f"Do not proceed with the {profile.home_currency} {request.requested_amount} request. None of the available options keeps the minimum balance protected."
    elif best_plan.plan_type == 'full_payment':
        if len(best_plan.spending_changes) > 0:
            affordability_status = 'affordable_with_plan'
            recommended_payment_method = 'full_payment'
            spending_changes_str = format_spending_changes(best_plan.spending_changes)
            explanation = f"Make spending changes ({spending_changes_str}), then pay {profile.home_currency} {request.requested_amount} today."
        else:
            affordability_status = 'affordable_now'
            recommended_payment_method = 'full_payment'
            spending_changes_str = 'none'
            explanation = f"Pay {profile.home_currency} {request.requested_amount} in full today on {request.request_date}. Minimum balance remains protected."
        final_plan_str = format_payment_plan(best_plan)
    elif best_plan.plan_type == 'installments':
        affordability_status = 'affordable_with_plan'
        recommended_payment_method = 'installments'
        spending_changes_str = format_spending_changes(best_plan.spending_changes)
        final_plan_str = format_payment_plan(best_plan)
        explanation = f"{best_plan.explanation} starting {best_plan.payments[0][0]}. Total payable is {profile.home_currency} {best_plan.total_amount}."
    elif best_plan.plan_type == 'partial_payment':
        affordability_status = 'affordable_with_plan'
        recommended_payment_method = 'partial_payment'
        spending_changes_str = 'none'
        final_plan_str = format_payment_plan(best_plan)
        explanation = f"Pay {profile.home_currency} {amount_safe_now} today and remaining {request.requested_amount - amount_safe_now} on {earliest_full_date}."
    elif best_plan.plan_type == 'wait':
        affordability_status = 'affordable_later'
        recommended_payment_method = 'wait'
        spending_changes_str = 'none'
        final_plan_str = format_payment_plan(best_plan)
        explanation = f"Wait until {earliest_full_date}, then pay {profile.home_currency} {request.requested_amount} in full."
    else:
        affordability_status = 'not_affordable'
        recommended_payment_method = 'not_recommended'
        final_plan_str = 'none'
        spending_changes_str = 'none'
        explanation = f"Do not proceed with this payment by {request.desired_completion_date}."

    # Earliest date for full payment
    if affordability_status == 'affordable_now':
        final_earliest_date = request.request_date
    else:
        final_earliest_date = earliest_full_date

    # Find the most relevant rejected plan safety check if unfeasible
    primary_safety_check = None
    if best_plan is None:
        for ep in trace.evaluated_plans:
            if ep.safety_check and not ep.safety_check.is_safe:
                primary_safety_check = ep.safety_check
                break

    # Concise user explanation
    explanation = generate_concise_explanation(
        request=request,
        profile=profile,
        plan=best_plan,
        earliest_full_date=final_earliest_date,
        safety_check=primary_safety_check
    )

    trace.concise_user_explanation = explanation
    trace.earliest_safe_full_payment_date = final_earliest_date
    if best_plan:
        trace.spending_changes = [c.to_str() for c in best_plan.spending_changes]
        trace.selected_plan = {
            "plan_type": best_plan.plan_type,
            "option_id": best_plan.option_id,
            "total_amount": str(best_plan.total_amount),
            "payments": [(p[0].strftime("%Y-%m-%d"), str(p[1])) for p in best_plan.payments],
            "spending_changes": [c.to_str() for c in best_plan.spending_changes]
        }
    else:
        trace.spending_changes = []
        trace.selected_plan = None

    decision = Decision(
        request_id=request.request_id,
        amount_safe_to_pay=amount_safe_now,
        affordability_status=affordability_status,
        recommended_payment_method=recommended_payment_method,
        payment_plan=final_plan_str,
        earliest_date_for_full_payment=final_earliest_date,
        spending_changes_needed=spending_changes_str,
        decision_explanation=explanation
    )

    return decision, trace
