from typing import List, Dict
from src.models.domain import FinancialProfile, FinancialEvent, Request, PaymentOption, Decision

def validate_profiles(profiles: List[FinancialProfile]) -> List[str]:
    errors = []
    seen = set()
    for p in profiles:
        if p.user_id in seen:
            errors.append(f"Duplicate user_id: {p.user_id}")
        seen.add(p.user_id)
        if p.current_available_balance is None:
            errors.append(f"User {p.user_id} has None available balance")
        if p.minimum_balance_to_keep is None:
            errors.append(f"User {p.user_id} has None minimum balance")
        if p.home_currency not in {'INR', 'EUR', 'IDR', 'USD', 'ZAR'}:
            errors.append(f"User {p.user_id} has unrecognized currency: {p.home_currency}")
    return errors

def validate_events(events: List[FinancialEvent]) -> List[str]:
    errors = []
    seen = set()
    valid_status = {'settled', 'pending', 'scheduled', 'cancelled', 'failed', 'unrealized'}
    valid_dir = {'debit', 'credit', 'non_cash'}
    for e in events:
        if e.event_id in seen:
            errors.append(f"Duplicate event_id: {e.event_id}")
        seen.add(e.event_id)
        if e.status not in valid_status:
            errors.append(f"Event {e.event_id} invalid status: {e.status}")
        if e.direction not in valid_dir:
            errors.append(f"Event {e.event_id} invalid direction: {e.direction}")
    return errors

def validate_requests(requests: List[Request]) -> List[str]:
    errors = []
    seen = set()
    for r in requests:
        if r.request_id in seen:
            errors.append(f"Duplicate request_id: {r.request_id}")
        seen.add(r.request_id)
        if r.requested_amount is None or r.requested_amount <= 0:
            errors.append(f"Request {r.request_id} non-positive requested amount: {r.requested_amount}")
        if r.request_date and r.desired_completion_date and r.desired_completion_date < r.request_date:
            errors.append(f"Request {r.request_id} completion date before request date")
    return errors

def validate_payment_options(options: Dict[str, List[PaymentOption]]) -> List[str]:
    errors = []
    for req_id, opts in options.items():
        if len(opts) < 2:
            errors.append(f"Request {req_id} has fewer than 2 payment options ({len(opts)})")
        for opt in opts:
            if opt.payment_method not in {'full_payment', 'installments'}:
                errors.append(f"Option {opt.payment_option_id} unknown payment method: {opt.payment_method}")
            if opt.financing_fee < 0:
                errors.append(f"Option {opt.payment_option_id} negative financing fee")
    return errors

def validate_output_row(decision: Decision) -> List[str]:
    errors = []
    valid_status = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
    valid_method = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}
    
    if decision.affordability_status not in valid_status:
        errors.append(f"Invalid affordability_status: {decision.affordability_status}")
    if decision.recommended_payment_method not in valid_method:
        errors.append(f"Invalid recommended_payment_method: {decision.recommended_payment_method}")
    if decision.amount_safe_to_pay < 0:
        errors.append(f"Negative amount_safe_to_pay: {decision.amount_safe_to_pay}")
    return errors
