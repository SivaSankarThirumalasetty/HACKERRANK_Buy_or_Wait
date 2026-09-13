from decimal import Decimal, ROUND_DOWN
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional
from src.models.domain import FinancialProfile, FinancialEvent, Request
from src.currency.converter import ExchangeRateTable
from src.evidence.messages import MessageAmendment, apply_amendments_to_events
from src.normalization.events import detect_recurring_events, project_recurring_events

def calculate_reference_amount_safe_to_pay(
    request: Request,
    profile: FinancialProfile,
    events: List[FinancialEvent],
    fx_table: ExchangeRateTable,
    amendments: Optional[List[MessageAmendment]] = None
) -> Tuple[Decimal, Dict]:
    req_date = request.request_date
    horizon_end = req_date + timedelta(days=90)
    user_id = profile.user_id

    # Filter events for this user
    user_events = [e for e in events if e.user_id == user_id]

    # 1. Project recurring streams
    detected = detect_recurring_events(user_events, user_id, req_date)
    projected = project_recurring_events(detected, req_date, horizon_end, user_id)
    all_events = detected + projected

    # 2. Apply message amendments
    if amendments:
        all_events = apply_amendments_to_events(all_events, amendments, profile, req_date, horizon_end)

    # 3. Handle cash-state rules:
    # - Reserve pending debits: immediately deducted from starting balance
    # - Pending credits: NOT counted
    # - Cancelled, failed, unrealized: excluded
    # - Non-cash: excluded
    # - Confirmed scheduled/settled: included on settlement_date
    pending_debit_reserve = Decimal('0')
    flow_events = []

    for ev in all_events:
        if ev.status in ['cancelled', 'failed', 'unrealized']:
            continue
        if ev.direction == 'non_cash':
            continue
        if ev.direction == 'credit' and ev.status == 'pending':
            # Do NOT count pending credits
            continue
        if ev.direction == 'debit' and ev.status == 'pending':
            # Reserve pending debit in home currency
            if ev.amount:
                home_amt = fx_table.to_home_currency(ev.amount, ev.currency, profile.home_currency, req_date)
                pending_debit_reserve += home_amt
            continue
        
        flow_events.append(ev)

    starting_balance = profile.current_available_balance - pending_debit_reserve
    running_balance = starting_balance

    daily_margins = {}
    curr_date = req_date
    min_margin = request.requested_amount
    min_margin_date = req_date

    for day_idx in range(91):
        day_credits = Decimal('0')
        day_debits = Decimal('0')

        for ev in flow_events:
            if ev.settlement_date == curr_date and ev.amount and ev.amount > Decimal('0'):
                home_amt = fx_table.to_home_currency(ev.amount, ev.currency, profile.home_currency, curr_date)
                if ev.direction == 'credit':
                    day_credits += home_amt
                elif ev.direction == 'debit':
                    day_debits += home_amt

        closing_balance = running_balance + day_credits - day_debits
        margin = closing_balance - profile.minimum_balance_to_keep
        daily_margins[curr_date] = {
            'closing_balance': closing_balance,
            'margin': margin,
            'credits': day_credits,
            'debits': day_debits
        }

        if margin < min_margin:
            min_margin = margin
            min_margin_date = curr_date

        running_balance = closing_balance
        curr_date += timedelta(days=1)

    # Calculate max safe payment x
    if min_margin < Decimal('0'):
        safe_x = Decimal('0')
    else:
        safe_x = (min_margin * 100).quantize(Decimal('1'), rounding=ROUND_DOWN) / 100
        if safe_x > request.requested_amount:
            safe_x = request.requested_amount

    diagnostics = {
        'starting_balance': starting_balance,
        'pending_debit_reserve': pending_debit_reserve,
        'min_margin': min_margin,
        'min_margin_date': min_margin_date,
        'daily_margins': daily_margins
    }

    return safe_x, diagnostics
