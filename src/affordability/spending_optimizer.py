from decimal import Decimal
from datetime import date, timedelta
from typing import List, Tuple, Optional, Dict
from itertools import combinations, permutations
import copy

from src.models.domain import FinancialProfile, FinancialEvent, Request, ForecastDay, PaymentPlan
from src.models.spending_change import SpendingChange
from src.currency.converter import ExchangeRateTable
from src.forecasting.cashflow import build_cashflow_forecast
from src.payment_plans.generator import is_schedule_safe
from src.normalization.events import detect_recurring_events
from src.evidence.messages import MessageAmendment

def get_candidate_flexible_events(
    profile: FinancialProfile,
    events: List[FinancialEvent],
    request_date: date
) -> List[Tuple[FinancialEvent, bool, bool]]:
    """
    Identifies candidate recurring flexible expenses that can be stopped or reduced.
    Constraints:
    1. Only recurring flexible expenses.
    2. Never modify protected categories.
    3. Respect user willingness to stop / reduce.
    Returns list of (ev, can_stop, can_reduce).
    """
    detected = detect_recurring_events(events, profile.user_id, request_date)
    recurring_events = [
        e for e in detected 
        if e.is_recurring and e.status == 'settled' and e.amount and e.amount > Decimal('0') and e.direction == 'debit'
    ]
    
    # De-duplicate by category + event_type to get primary templates (latest settled)
    seen_events: Dict[Tuple[str, str], FinancialEvent] = {}
    for ev in sorted(recurring_events, key=lambda x: x.settlement_date):
        if ev.category in profile.expense_categories_to_protect:
            continue
        seen_events[(ev.category, ev.event_type)] = ev

    candidates: List[Tuple[FinancialEvent, bool, bool]] = []
    for (cat, etype), ev in seen_events.items():
        can_stop = (
            ev.flexibility in ['stoppable', 'reducible_or_stoppable'] and 
            ev.category in profile.expense_categories_to_stop
        )
        can_reduce = (
            ev.flexibility in ['reducible', 'reducible_or_stoppable'] and 
            ev.category in profile.expense_categories_to_reduce
        )
        if can_stop or can_reduce:
            candidates.append((ev, can_stop, can_reduce))
            
    return candidates

def _binary_search_reduction(
    ev: FinancialEvent,
    fixed_changes: List[SpendingChange],
    payments: List[Tuple[date, Decimal]],
    profile: FinancialProfile,
    events: List[FinancialEvent],
    request_date: date,
    fx_table: ExchangeRateTable,
    amendments: Optional[List[MessageAmendment]]
) -> Optional[Decimal]:
    """
    Finds the exact smallest reduction in [0.01, max_reduction] for ev
    that makes payments safe alongside fixed_changes.
    Returns smallest reduction (Decimal) or None if even max reduction is insufficient.
    """
    min_allowed = ev.minimum_allowed_amount if ev.minimum_allowed_amount is not None else Decimal('0.01')
    max_reduction = ev.amount - min_allowed
    if max_reduction <= Decimal('0'):
        return None

    # 1. Test whether maximum reduction makes the plan safe
    max_change = SpendingChange(action='reduce_to', event_id=ev.event_id, new_amount=min_allowed)
    fc_max = build_cashflow_forecast(profile, events, request_date, fx_table, amendments, fixed_changes + [max_change])
    if not is_schedule_safe(payments, fc_max, profile.minimum_balance_to_keep):
        return None  # Even maximum permitted reduction is not enough

    # 2. Binary search across integer cents for exact precision and monotonicity
    low_cents = 1
    high_cents = int((max_reduction * 100).quantize(Decimal('1')))
    best_cents = high_cents

    while low_cents <= high_cents:
        mid_cents = (low_cents + high_cents) // 2
        mid_reduction = Decimal(mid_cents) / Decimal(100)
        mid_new_amt = ev.amount - mid_reduction
        test_change = SpendingChange(action='reduce_to', event_id=ev.event_id, new_amount=mid_new_amt)
        fc_mid = build_cashflow_forecast(profile, events, request_date, fx_table, amendments, fixed_changes + [test_change])
        if is_schedule_safe(payments, fc_mid, profile.minimum_balance_to_keep):
            best_cents = mid_cents
            high_cents = mid_cents - 1  # try a smaller reduction
        else:
            low_cents = mid_cents + 1  # need larger reduction

    return Decimal(best_cents) / Decimal(100)

def optimize_spending_for_schedule(
    payments: List[Tuple[date, Decimal]],
    profile: FinancialProfile,
    events: List[FinancialEvent],
    request_date: date,
    fx_table: ExchangeRateTable,
    amendments: Optional[List[MessageAmendment]],
    candidate_events: List[Tuple[FinancialEvent, bool, bool]]
) -> Optional[Tuple[Decimal, List[SpendingChange]]]:
    """
    Deterministically calculates the optimal spending changes (up to 3 actions)
    to make payments safe.
    Prefers the smallest total spending reduction in home currency.
    Returns (total_reduction_home, spending_changes) or None if no combination is sufficient.
    """
    if not candidate_events:
        return None

    # Generate single actions per event
    single_actions: List[Tuple[FinancialEvent, str]] = []
    for ev, can_stop, can_reduce in candidate_events:
        if can_stop:
            single_actions.append((ev, 'stop'))
        if can_reduce:
            single_actions.append((ev, 'reduce_to'))

    # Generate combinations of 1, 2, or 3 actions without reusing the same event
    action_combos: List[List[Tuple[FinancialEvent, str]]] = []
    for k in range(1, min(4, len(candidate_events) + 1)):
        for combo in combinations(single_actions, k):
            ev_ids = [ev.event_id for ev, act in combo]
            if len(ev_ids) == len(set(ev_ids)):  # mutually exclusive per event
                action_combos.append(list(combo))

    valid_solutions: List[Tuple[Decimal, int, List[SpendingChange]]] = []

    for spec in action_combos:
        stop_evs = [ev for ev, act in spec if act == 'stop']
        red_evs = [ev for ev, act in spec if act == 'reduce_to']

        stop_changes = [SpendingChange(action='stop', event_id=ev.event_id) for ev in stop_evs]
        stop_reduction_home = sum(
            fx_table.to_home_currency(ev.amount, ev.currency, profile.home_currency, request_date)
            for ev in stop_evs
        )

        if not red_evs:
            # Case 1: All actions are stop
            fc = build_cashflow_forecast(profile, events, request_date, fx_table, amendments, stop_changes)
            if is_schedule_safe(payments, fc, profile.minimum_balance_to_keep):
                valid_solutions.append((stop_reduction_home, len(stop_changes), stop_changes))

        elif len(red_evs) == 1:
            # Case 2: Exactly 1 action is reduce_to
            ev_red = red_evs[0]

            # Rule 7: Do not make unnecessary reductions.
            # If stop actions alone are already sufficient, do not reduce ev_red.
            if stop_changes:
                fc_stop = build_cashflow_forecast(profile, events, request_date, fx_table, amendments, stop_changes)
                if is_schedule_safe(payments, fc_stop, profile.minimum_balance_to_keep):
                    continue

            # Binary search smallest reduction
            smallest_red = _binary_search_reduction(
                ev=ev_red,
                fixed_changes=stop_changes,
                payments=payments,
                profile=profile,
                events=events,
                request_date=request_date,
                fx_table=fx_table,
                amendments=amendments
            )
            if smallest_red is not None:
                new_amt = (ev_red.amount - smallest_red).quantize(Decimal('0.01'))
                sc_red = SpendingChange(action='reduce_to', event_id=ev_red.event_id, new_amount=new_amt)
                total_changes = stop_changes + [sc_red]
                red_reduction_home = fx_table.to_home_currency(smallest_red, ev_red.currency, profile.home_currency, request_date)
                total_reduction_home = stop_reduction_home + red_reduction_home
                valid_solutions.append((total_reduction_home, len(total_changes), total_changes))

        else:
            # Case 3: Multiple reduce_to actions (e.g. 2 reduce_to events)
            # Try permutations where earlier events are at max reduction and last event is binary-searched
            for p_order in permutations(red_evs):
                fixed_red_changes = list(stop_changes)
                fixed_red_home = stop_reduction_home
                all_valid = True

                for ev_prev in p_order[:-1]:
                    min_allowed = ev_prev.minimum_allowed_amount if ev_prev.minimum_allowed_amount is not None else Decimal('0.01')
                    max_r = ev_prev.amount - min_allowed
                    if max_r <= Decimal('0'):
                        all_valid = False
                        break
                    fixed_red_changes.append(SpendingChange(action='reduce_to', event_id=ev_prev.event_id, new_amount=min_allowed))
                    fixed_red_home += fx_table.to_home_currency(max_r, ev_prev.currency, profile.home_currency, request_date)

                if not all_valid:
                    continue

                last_ev = p_order[-1]
                smallest_red = _binary_search_reduction(
                    ev=last_ev,
                    fixed_changes=fixed_red_changes,
                    payments=payments,
                    profile=profile,
                    events=events,
                    request_date=request_date,
                    fx_table=fx_table,
                    amendments=amendments
                )
                if smallest_red is not None:
                    new_amt = (last_ev.amount - smallest_red).quantize(Decimal('0.01'))
                    sc_last = SpendingChange(action='reduce_to', event_id=last_ev.event_id, new_amount=new_amt)
                    total_changes = fixed_red_changes + [sc_last]
                    last_red_home = fx_table.to_home_currency(smallest_red, last_ev.currency, profile.home_currency, request_date)
                    tot_reduction = fixed_red_home + last_red_home
                    valid_solutions.append((tot_reduction, len(total_changes), total_changes))

    if not valid_solutions:
        return None

    # Ranking:
    # 1. Smallest total spending reduction in home currency
    # 2. Fewer spending changes
    # 3. Deterministic tie-breaker by event_id
    valid_solutions.sort(key=lambda s: (s[0], s[1], [c.event_id for c in s[2]]))
    best = valid_solutions[0]
    return (best[0], best[2])
