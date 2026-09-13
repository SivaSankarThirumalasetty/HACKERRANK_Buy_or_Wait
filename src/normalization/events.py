from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict
from collections import defaultdict, Counter
import copy
import calendar
from decimal import Decimal

from src.models.domain import FinancialEvent
from src.models.recurring_stream import RecurringStream
from src.evidence.images import apply_image_amounts

def normalize_events(events: List[FinancialEvent]) -> List[FinancialEvent]:
    return apply_image_amounts(events)

def get_cash_effective_events(events: List[FinancialEvent]) -> List[FinancialEvent]:
    res = []
    for ev in events:
        if ev.status in ['cancelled', 'failed', 'unrealized']:
            continue
        if ev.direction == 'non_cash':
            continue
        if ev.direction == 'credit' and ev.status == 'pending':
            continue
        res.append(ev)
    return res

def get_spendable_debits(events: List[FinancialEvent], categories_to_protect: List[str]) -> List[FinancialEvent]:
    res = []
    for ev in events:
        if ev.direction == 'debit' and ev.flexibility in ['stoppable', 'reducible', 'reducible_or_stoppable']:
            if ev.category not in categories_to_protect:
                res.append(ev)
    return res

def is_month_end(d: date) -> bool:
    return d.day == calendar.monthrange(d.year, d.month)[1]

def add_calendar_month(base_date: date, day_of_month: int, is_last_day: bool) -> date:
    year = base_date.year
    month = base_date.month + 1
    if month > 12:
        year += 1
        month = 1
    max_days = calendar.monthrange(year, month)[1]
    if is_last_day:
        target_day = max_days
    else:
        target_day = min(day_of_month, max_days)
    return date(year, month, target_day)

def determine_stream_cadence_full(dates: List[date]) -> Tuple[Optional[str], Optional[int], Optional[int], bool]:
    """
    Evaluates chronological settlement/event dates to identify cadence.
    Supports weekly, biweekly, calendar-monthly, fixed-day monthly, and regular intervals.
    Returns: (cadence, period_days, day_of_month, is_month_end)
    """
    if len(dates) < 2:
        return None, None, None, False

    diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
    avg_diff = sum(diffs) / len(diffs)

    # 1. Weekly check (diffs around 7 days, 6-8)
    if all(6 <= d <= 8 for d in diffs) or (len(diffs) >= 2 and 6.5 <= avg_diff <= 7.5):
        return 'weekly', 7, None, False

    # 2. Biweekly check (diffs around 14 days, 12-16)
    if all(12 <= d <= 16 for d in diffs) or (len(diffs) >= 2 and 13.0 <= avg_diff <= 15.0):
        return 'biweekly', 14, None, False

    # 3. Monthly check: distinguish calendar-monthly vs fixed-days
    # Check if all dates are month-end
    if all(is_month_end(d) for d in dates):
        return 'monthly_calendar', 30, 31, True

    days_of_month = [d.day for d in dates]
    c_days = Counter(days_of_month)
    mode_day, mode_count = c_days.most_common(1)[0]
    
    is_consistent_dom = (max(days_of_month) - min(days_of_month) <= 3)
    consistent_monthly_diffs = all(26 <= d <= 33 for d in diffs)
    diff_spread = max(diffs) - min(diffs)

    # If days of month are consistent (+/- 3 days around target day across consecutive months),
    # it is calendar-monthly recurrence (e.g. paying around the 15th every calendar month)
    if is_consistent_dom and consistent_monthly_diffs:
        is_end = (mode_day >= 28 and all(is_month_end(d) for d in dates if d.day in [28, 29, 30, 31]))
        target_day = 31 if is_end else mode_day
        return 'monthly_calendar', 30, target_day, is_end

    # If diffs are strictly exactly 30 days every single time, but days of month wander
    if all(d == 30 for d in diffs):
        return 'fixed_days', 30, None, False

    # Check if days of month are identical/consistent (+/- 3 days) across dates,
    # even if an intermediate month was skipped (e.g. diffs ~30 or ~60)
    if is_consistent_dom and all(26 <= d <= 33 or 56 <= d <= 64 for d in diffs):
        is_end = (mode_day >= 28 and all(is_month_end(d) for d in dates if d.day in [28, 29, 30, 31]))
        target_day = 31 if is_end else mode_day
        return 'monthly_calendar', 30, target_day, is_end

    # 4. Other regular intervals
    if 19 <= avg_diff <= 23 and diff_spread <= 4:
        return 'irregular', 21, None, False

    return None, None, None, False

def determine_stream_cadence(dates: List[date]) -> Tuple[Optional[str], Optional[int]]:
    """
    Backwards-compatible wrapper returning (cadence, period_days).
    For monthly calendar streams, maps 'monthly_calendar' to 'monthly'.
    """
    cadence, period, _, _ = determine_stream_cadence_full(dates)
    if cadence == 'monthly_calendar':
        return 'monthly', period
    return cadence, period

def build_recurring_streams(
    base_events: List[FinancialEvent],
    user_id: str,
    as_of_date: date,
    horizon_end: Optional[date] = None
) -> List[RecurringStream]:
    """
    Identifies all historical settled streams, determines cadence,
    binds existing scheduled future events as authoritative overrides,
    and returns canonical RecurringStream objects.
    """
    if horizon_end is None:
        horizon_end = as_of_date + timedelta(days=90)

    # Group settled events up to as_of_date
    settled_groups = defaultdict(list)
    for ev in base_events:
        if ev.user_id == user_id and ev.status == 'settled' and ev.event_date <= as_of_date:
            settled_groups[(ev.category, ev.event_type, ev.currency)].append(ev)

    # Group scheduled future events
    scheduled_groups = defaultdict(list)
    for ev in base_events:
        if ev.user_id == user_id and ev.status == 'scheduled' and ev.event_date >= as_of_date:
            scheduled_groups[(ev.category, ev.event_type, ev.currency)].append(ev)

    streams: List[RecurringStream] = []

    for key, group in settled_groups.items():
        if len(group) < 2:
            continue

        cat, etype, cur = key
        group.sort(key=lambda x: x.event_date)
        dates = [e.event_date for e in group]
        cadence, period, dom, is_end = determine_stream_cadence_full(dates)

        if not cadence or not period:
            continue

        sched_overrides = scheduled_groups.get(key, [])
        sched_overrides.sort(key=lambda x: x.event_date)

        last_ev = group[-1]
        base_amt = last_ev.amount if last_ev.amount is not None else Decimal('0')

        stream = RecurringStream(
            stream_id=f"stream_{user_id}_{cat}_{etype}",
            user_id=user_id,
            category=cat,
            event_type=etype,
            direction=last_ev.direction,
            currency=cur,
            cadence=cadence,
            period_days=period,
            amount_rule='last_known',
            base_amount=base_amt,
            day_of_month=dom,
            is_month_end=is_end,
            historical_evidence=group,
            scheduled_overrides=sched_overrides,
            cancellation_date=None,
            projected_occurrences=[]
        )
        streams.append(stream)

    return streams

def detect_recurring_events(events: List[FinancialEvent], user_id: str, as_of_date: date) -> List[FinancialEvent]:
    new_events = [copy.copy(ev) for ev in events]
    streams = build_recurring_streams(new_events, user_id, as_of_date)
    
    stream_event_ids = set()
    period_map = {}
    for s in streams:
        for ev in s.historical_evidence:
            stream_event_ids.add(ev.event_id)
            period_map[ev.event_id] = s.period_days

    for ev in new_events:
        if ev.event_id in stream_event_ids:
            ev.is_recurring = True
            ev.recurrence_period_days = period_map.get(ev.event_id)

    return new_events

def project_recurring_events(
    base_events: List[FinancialEvent],
    from_date: date,
    to_date: date,
    user_id: str
) -> List[FinancialEvent]:
    """
    Projects recurring occurrences across the forecast horizon:
    1. Determines stream cadence from historical evidence (calendar-month vs fixed-days).
    2. Identifies existing scheduled future events.
    3. Uses scheduled events as authoritative for dates where they exist.
    4. Fills missing future recurrence dates around those scheduled events.
    5. Never suppresses the entire stream merely because one scheduled event exists.
    6. Prevents duplicate projected events.
    """
    streams = build_recurring_streams(base_events, user_id, from_date, to_date)
    all_projected: List[FinancialEvent] = []

    for stream in streams:
        if not stream.period_days or not stream.historical_evidence:
            continue

        last_settled = stream.historical_evidence[-1]
        period = stream.period_days
        is_cal_month = (stream.cadence == 'monthly_calendar')
        dom = stream.day_of_month if stream.day_of_month is not None else last_settled.event_date.day
        is_end = stream.is_month_end

        # Helper to step date forward by one cadence step
        def next_occurrence(curr: date) -> date:
            if is_cal_month:
                return add_calendar_month(curr, dom, is_end)
            else:
                return curr + timedelta(days=period)

        # Collect dates of existing scheduled overrides in this window
        sched_dates = [e.event_date for e in stream.scheduled_overrides]
        
        # Determine candidate projection dates from last_settled forward
        projected_dates = []
        next_date = next_occurrence(last_settled.event_date)
        
        while next_date <= to_date:
            if next_date >= from_date:
                # Collision check: do not project if an authoritative scheduled event
                # exists close to this cadence date (within period / 2 days, min 2)
                has_override = any(abs((next_date - s_date).days) <= max(2, period // 2) for s_date in sched_dates)
                if not has_override:
                    projected_dates.append(next_date)
            next_date = next_occurrence(next_date)

        # Also project forward from any scheduled overrides if they extend the stream
        if stream.scheduled_overrides:
            last_sched = stream.scheduled_overrides[-1]
            fwd_date = next_occurrence(last_sched.event_date)
            while fwd_date <= to_date:
                if fwd_date >= from_date:
                    has_override = any(abs((fwd_date - s_date).days) <= max(2, period // 2) for s_date in sched_dates)
                    has_proj = any(abs((fwd_date - p_date).days) <= max(2, period // 2) for p_date in projected_dates)
                    if not has_override and not has_proj:
                        projected_dates.append(fwd_date)
                fwd_date = next_occurrence(fwd_date)

        # Sort and deduplicate projection dates
        projected_dates = sorted(list(set(projected_dates)))

        c = 1
        for p_date in projected_dates:
            proj = copy.copy(last_settled)
            proj.event_id = f"proj_{last_settled.event_id}_{c}"
            proj.event_date = p_date
            proj.settlement_date = p_date
            proj.status = 'scheduled'
            proj.is_recurring = True
            proj.recurrence_period_days = period
            all_projected.append(proj)
            stream.projected_occurrences.append(proj)
            c += 1

    return all_projected
