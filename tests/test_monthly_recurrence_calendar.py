import pytest
from datetime import date
from decimal import Decimal
from src.models.domain import FinancialEvent
from src.normalization.events import (
    determine_stream_cadence_full,
    determine_stream_cadence,
    build_recurring_streams,
    project_recurring_events,
    add_calendar_month
)

def test_jan_31_monthly_calendar_progression():
    history = [
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31)
    ]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert is_end is True

    d1 = add_calendar_month(date(2026, 1, 31), dom, is_end)
    assert d1 == date(2026, 2, 28)
    d2 = add_calendar_month(d1, dom, is_end)
    assert d2 == date(2026, 3, 31)
    d3 = add_calendar_month(d2, dom, is_end)
    assert d3 == date(2026, 4, 30)

def test_feb_28_monthly_progression():
    history = [date(2025, 1, 31), date(2025, 2, 28)]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert is_end is True
    d_mar = add_calendar_month(date(2025, 2, 28), dom, is_end)
    assert d_mar == date(2025, 3, 31)

def test_leap_year_feb_29():
    history = [date(2023, 12, 31), date(2024, 1, 31)]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert is_end is True

    d_feb = add_calendar_month(date(2024, 1, 31), dom, is_end)
    assert d_feb == date(2024, 2, 29)
    d_mar = add_calendar_month(d_feb, dom, is_end)
    assert d_mar == date(2024, 3, 31)

def test_jan_30_monthly_progression():
    history = [date(2025, 11, 30), date(2025, 12, 30), date(2026, 1, 30)]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert dom == 30

    d_feb = add_calendar_month(date(2026, 1, 30), dom, is_end)
    assert d_feb == date(2026, 2, 28)
    d_mar = add_calendar_month(d_feb, dom, is_end)
    assert d_mar == date(2026, 3, 30)
    d_apr = add_calendar_month(d_mar, dom, is_end)
    assert d_apr == date(2026, 4, 30)

def test_jan_29_monthly_progression():
    history = [date(2025, 11, 29), date(2025, 12, 29), date(2026, 1, 29)]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert dom == 29

    d_feb = add_calendar_month(date(2026, 1, 29), dom, is_end)
    assert d_feb == date(2026, 2, 28)
    d_mar = add_calendar_month(d_feb, dom, is_end)
    assert d_mar == date(2026, 3, 29)

def test_monthly_events_with_plus_minus_few_days():
    history = [date(2026, 1, 15), date(2026, 2, 14), date(2026, 3, 16)]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'monthly_calendar'
    assert dom in [14, 15, 16]

def test_fixed_30_day_events():
    history = [date(2026, 1, 1), date(2026, 1, 31), date(2026, 3, 2)]
    diffs = [(history[i] - history[i-1]).days for i in range(1, len(history))]
    assert diffs == [30, 30]
    cadence, period, dom, is_end = determine_stream_cadence_full(history)
    assert cadence == 'fixed_days'
    assert period == 30

def test_scheduled_override_between_projections():
    ev1 = FinancialEvent('ev1', 'u_test', date(2026, 1, 15), date(2026, 1, 15), 'expense', 'rent', Decimal('500'), 'USD', 'debit', 'settled', 'fixed', 'rent', None)
    ev2 = FinancialEvent('ev2', 'u_test', date(2026, 2, 15), date(2026, 2, 15), 'expense', 'rent', Decimal('500'), 'USD', 'debit', 'settled', 'fixed', 'rent', None)
    sched = FinancialEvent('sched1', 'u_test', date(2026, 3, 15), date(2026, 3, 15), 'expense', 'rent', Decimal('550'), 'USD', 'debit', 'scheduled', 'fixed', 'rent', None)

    events = [ev1, ev2, sched]
    projected = project_recurring_events(events, date(2026, 2, 16), date(2026, 5, 30), 'u_test')

    proj_dates = [p.event_date for p in projected]
    assert date(2026, 3, 15) not in proj_dates
    assert date(2026, 4, 15) in proj_dates
    assert date(2026, 5, 15) in proj_dates
