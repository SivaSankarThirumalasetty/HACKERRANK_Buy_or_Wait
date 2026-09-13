from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from src.models.domain import FinancialProfile, FinancialEvent, ForecastDay
from src.currency.converter import ExchangeRateTable
from src.evidence.messages import MessageAmendment

def compute_pending_debit_reserve(events: List[FinancialEvent], profile: FinancialProfile, fx_table: ExchangeRateTable, as_of_date: date) -> Decimal:
    reserve = Decimal('0')
    for ev in events:
        if ev.direction == 'debit' and ev.status == 'pending' and ev.amount:
            amt = fx_table.to_home_currency(ev.amount, ev.currency, profile.home_currency, as_of_date)
            reserve += amt
    return reserve

def get_adjusted_starting_balance(profile: FinancialProfile, events: List[FinancialEvent], fx_table: ExchangeRateTable, as_of_date: date) -> Decimal:
    reserve = compute_pending_debit_reserve(events, profile, fx_table, as_of_date)
    return profile.current_available_balance - reserve

def build_cashflow_forecast(
    profile: FinancialProfile,
    events: List[FinancialEvent],
    request_date: date,
    fx_table: ExchangeRateTable,
    amendments: List[MessageAmendment] = None,
    spending_changes: List = None
) -> List[ForecastDay]:
    from src.normalization.events import get_cash_effective_events, detect_recurring_events, project_recurring_events
    from src.evidence.messages import apply_amendments_to_events

    forecast_end = request_date + timedelta(days=90)
    
    # 1. Detect & project recurring events from settled history
    detected = detect_recurring_events(events, profile.user_id, request_date)
    projected = project_recurring_events(detected, request_date, forecast_end, profile.user_id)
    all_events = detected + projected

    # 2. Apply message amendments to the full active timeline
    if amendments:
        all_events = apply_amendments_to_events(all_events, amendments, profile, request_date, forecast_end)

    # 3. Filter cash-effective events
    effective_events = get_cash_effective_events(all_events)
    
    # Filter out pending debits from standard flow as they are reserved
    flow_events = [ev for ev in effective_events if not (ev.direction == 'debit' and ev.status == 'pending')]
    
    balance = get_adjusted_starting_balance(profile, all_events, fx_table, request_date)
    
    forecast = []
    curr_date = request_date
    for i in range(91):
        credits = Decimal('0')
        debits = Decimal('0')
        ev_ids = []
        
        for ev in flow_events:
            if ev.settlement_date == curr_date and ev.amount:
                # Apply spending change if any
                amt = ev.amount
                if spending_changes:
                    for sc in spending_changes:
                        if sc.event_id == ev.event_id or ev.event_id.startswith(f"proj_{sc.event_id}_"):
                            if sc.action == 'stop':
                                amt = Decimal('0')
                            elif sc.action == 'reduce_to' and sc.new_amount is not None:
                                amt = sc.new_amount
                
                if amt > 0:
                    home_amt = fx_table.to_home_currency(amt, ev.currency, profile.home_currency, curr_date)
                    if ev.direction == 'credit':
                        credits += home_amt
                    elif ev.direction == 'debit':
                        debits += home_amt
                    ev_ids.append(ev.event_id)
        
        opening = balance
        closing = balance + credits - debits
        
        forecast.append(ForecastDay(
            day=curr_date,
            opening_balance=opening,
            credits=credits,
            debits=debits,
            closing_balance=closing,
            events=ev_ids
        ))
        
        balance = closing
        curr_date += timedelta(days=1)
        
    return forecast

def get_minimum_balance_on_date(forecast: List[ForecastDay], target_date: date) -> Optional[Decimal]:
    for f in forecast:
        if f.day == target_date:
            return f.closing_balance
    return None

def is_balance_safe_throughout(forecast: List[ForecastDay], minimum_balance: Decimal, from_date: date, to_date: date) -> bool:
    for f in forecast:
        if from_date <= f.day <= to_date:
            if f.closing_balance < minimum_balance:
                return False
    return True

def get_balance_on_date(forecast: List[ForecastDay], target_date: date) -> Optional[Decimal]:
    for f in forecast:
        if f.day == target_date:
            return f.opening_balance
    return None
