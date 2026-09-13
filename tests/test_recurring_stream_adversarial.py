import pytest
from datetime import date, timedelta
from decimal import Decimal
from src.models.domain import FinancialEvent, FinancialProfile, Request, PaymentOption
from src.models.recurring_stream import RecurringStream
from src.normalization.events import (
    determine_stream_cadence,
    build_recurring_streams,
    detect_recurring_events,
    project_recurring_events
)
from src.evidence.messages import MessageAmendment, MessageEffect, apply_amendments_to_events
from src.currency.converter import ExchangeRateTable
from src.affordability.engine import make_decision

@pytest.fixture
def base_profile():
    return FinancialProfile(
        user_id='u_stream_test',
        home_currency='INR',
        current_available_balance=Decimal('50000'),
        minimum_balance_to_keep=Decimal('10000'),
        financial_priorities=['emergency_fund'],
        expense_categories_to_protect=['rent'],
        expense_categories_to_reduce=[],
        expense_categories_to_stop=[],
        payment_methods=['full_payment'],
        max_installment_months=None
    )

def test_adv_cadence_determination():
    # Weekly
    weekly_dates = [date(2025, 1, 1), date(2025, 1, 8), date(2025, 1, 15)]
    c, p = determine_stream_cadence(weekly_dates)
    assert c == 'weekly' and p == 7

    # Biweekly
    biweekly_dates = [date(2025, 1, 1), date(2025, 1, 15), date(2025, 1, 29)]
    c, p = determine_stream_cadence(biweekly_dates)
    assert c == 'biweekly' and p == 14

    # Monthly (same day of month)
    monthly_dates = [date(2025, 1, 15), date(2025, 2, 15), date(2025, 3, 15)]
    c, p = determine_stream_cadence(monthly_dates)
    assert c == 'monthly' and p == 30

    # Irregular / insufficient
    assert determine_stream_cadence([date(2025, 1, 1)]) == (None, None)

def test_adv_historical_plus_one_scheduled_future():
    # History: monthly salary on 1st of month.
    # Future: exactly one scheduled event on 2025-04-01.
    # Expectation: 2025-04-01 is kept authoritative, but future dates (2025-05-01, 2025-06-01) are projected.
    events = [
        FinancialEvent('s1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'income', 'salary', Decimal('20000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('s2', 'u1', date(2025, 2, 1), date(2025, 2, 1), 'income', 'salary', Decimal('20000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('s3', 'u1', date(2025, 3, 1), date(2025, 3, 1), 'income', 'salary', Decimal('20000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('sched1', 'u1', date(2025, 4, 1), date(2025, 4, 1), 'income', 'salary', Decimal('22000'), 'INR', 'credit', 'scheduled', 'fixed', 'salary', None),
    ]
    as_of = date(2025, 3, 15)
    horizon_end = as_of + timedelta(days=90)
    
    projected = project_recurring_events(events, as_of, horizon_end, 'u1')
    
    # Scheduled on 2025-04-01 must NOT be duplicated in projected
    proj_dates = [p.event_date for p in projected]
    assert date(2025, 4, 1) not in proj_dates
    # Stream must NOT be completely suppressed; future months must be projected
    assert any(d >= date(2025, 5, 1) for d in proj_dates)

def test_adv_multiple_scheduled_overrides():
    # History + 2 scheduled overrides
    events = [
        FinancialEvent('s1', 'u1', date(2025, 1, 15), date(2025, 1, 15), 'expense', 'gym', Decimal('1500'), 'INR', 'debit', 'settled', 'fixed', 'gym', None),
        FinancialEvent('s2', 'u1', date(2025, 2, 15), date(2025, 2, 15), 'expense', 'gym', Decimal('1500'), 'INR', 'debit', 'settled', 'fixed', 'gym', None),
        FinancialEvent('sched1', 'u1', date(2025, 3, 15), date(2025, 3, 15), 'expense', 'gym', Decimal('1500'), 'INR', 'debit', 'scheduled', 'fixed', 'gym', None),
        FinancialEvent('sched2', 'u1', date(2025, 4, 15), date(2025, 4, 15), 'expense', 'gym', Decimal('1500'), 'INR', 'debit', 'scheduled', 'fixed', 'gym', None),
    ]
    as_of = date(2025, 3, 1)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u1')
    proj_dates = [p.event_date for p in projected]
    # No duplicate on 3-15 or 4-15
    assert date(2025, 3, 15) not in proj_dates
    assert date(2025, 4, 15) not in proj_dates
    # Later dates (e.g. May) are generated
    assert any(d >= date(2025, 5, 10) for d in proj_dates)

def test_adv_salary_increase_amendment(base_profile):
    events = [
        FinancialEvent('s1', 'u_stream_test', date(2025, 1, 1), date(2025, 1, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('s2', 'u_stream_test', date(2025, 2, 1), date(2025, 2, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
    ]
    as_of = date(2025, 2, 15)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u_stream_test')
    
    amendment = MessageAmendment(
        effect=MessageEffect.SALARY_INCREASE,
        new_amount=Decimal('45000'),
        new_currency='INR',
        effective_date=date(2025, 3, 1),
        is_one_time=False,
        source_user_id='u_stream_test',
        source_message_id='m1'
    )
    amended = apply_amendments_to_events(events + projected, [amendment], base_profile, as_of, horizon_end)
    future_salaries = [e for e in amended if e.category == 'salary' and e.settlement_date >= as_of]
    assert len(future_salaries) >= 2
    assert all(e.amount == Decimal('45000') for e in future_salaries)

def test_adv_salary_decrease_temporary(base_profile):
    events = [
        FinancialEvent('s1', 'u_stream_test', date(2025, 1, 1), date(2025, 1, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('s2', 'u_stream_test', date(2025, 2, 1), date(2025, 2, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
    ]
    as_of = date(2025, 2, 15)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u_stream_test')
    
    amendment = MessageAmendment(
        effect=MessageEffect.SALARY_DECREASE_TEMP,
        new_amount=Decimal('20000'),
        new_currency='INR',
        effective_date=None,
        is_one_time=True,
        source_user_id='u_stream_test',
        source_message_id='m2'
    )
    amended = apply_amendments_to_events(events + projected, [amendment], base_profile, as_of, horizon_end)
    future_salaries = [e for e in amended if e.category == 'salary' and e.settlement_date >= as_of]
    future_salaries.sort(key=lambda x: x.settlement_date)
    # Only first upcoming is decreased to 20000
    assert future_salaries[0].amount == Decimal('20000')
    # Subsequent return to 30000
    assert future_salaries[1].amount == Decimal('30000')

def test_adv_cancelled_salary(base_profile):
    events = [
        FinancialEvent('s1', 'u_stream_test', date(2025, 1, 1), date(2025, 1, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
        FinancialEvent('s2', 'u_stream_test', date(2025, 2, 1), date(2025, 2, 1), 'income', 'salary', Decimal('30000'), 'INR', 'credit', 'settled', 'fixed', 'salary', None),
    ]
    as_of = date(2025, 2, 15)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u_stream_test')
    
    amendment = MessageAmendment(
        effect=MessageEffect.EMPLOYMENT_ENDED,
        new_amount=None,
        new_currency=None,
        effective_date=date(2025, 3, 1),
        is_one_time=False,
        source_user_id='u_stream_test',
        source_message_id='m3'
    )
    amended = apply_amendments_to_events(events + projected, [amendment], base_profile, as_of, horizon_end)
    future_salaries = [e for e in amended if e.category == 'salary' and e.settlement_date >= as_of]
    assert all(e.status == 'cancelled' for e in future_salaries)

def test_adv_rent_increase_12pct(base_profile):
    events = [
        FinancialEvent('r1', 'u_stream_test', date(2025, 1, 5), date(2025, 1, 5), 'expense', 'rent', Decimal('10000'), 'INR', 'debit', 'settled', 'fixed', 'rent', None),
        FinancialEvent('r2', 'u_stream_test', date(2025, 2, 5), date(2025, 2, 5), 'expense', 'rent', Decimal('10000'), 'INR', 'debit', 'settled', 'fixed', 'rent', None),
    ]
    as_of = date(2025, 2, 15)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u_stream_test')
    
    amendment = MessageAmendment(
        effect=MessageEffect.RENT_INCREASE_12PCT,
        new_amount=None,
        new_currency=None,
        effective_date=date(2025, 3, 1),
        is_one_time=False,
        source_user_id='u_stream_test',
        source_message_id='m4'
    )
    amended = apply_amendments_to_events(events + projected, [amendment], base_profile, as_of, horizon_end)
    future_rents = [e for e in amended if 'rent' in e.category and e.settlement_date >= as_of]
    assert len(future_rents) >= 2
    assert all(e.amount == Decimal('11200.00') for e in future_rents)

def test_adv_missing_month_stream():
    # Stream with missing month: Jan 1, Feb 1, Apr 1 (missed Mar 1)
    dates = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 4, 1)]
    c, p = determine_stream_cadence(dates)
    # Should still recognize monthly recurrence cadence of 30 days
    assert c == 'monthly' and p == 30

def test_adv_prevent_duplicate_recurrence():
    # If two events are settled very close together by anomaly, cadence check ensures uniqueness
    events = [
        FinancialEvent('d1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'expense', 'sub', Decimal('500'), 'INR', 'debit', 'settled', 'fixed', 'sub', None),
        FinancialEvent('d2', 'u1', date(2025, 2, 1), date(2025, 2, 1), 'expense', 'sub', Decimal('500'), 'INR', 'debit', 'settled', 'fixed', 'sub', None),
    ]
    as_of = date(2025, 2, 15)
    horizon_end = as_of + timedelta(days=90)
    projected = project_recurring_events(events, as_of, horizon_end, 'u1')
    proj_dates = [p.event_date for p in projected]
    # Dates must be strictly distinct
    assert len(proj_dates) == len(set(proj_dates))

def test_adv_irregular_dates():
    # Randomly spaced events: Day 1, Day 12, Day 45, Day 89
    dates = [date(2025, 1, 1), date(2025, 1, 12), date(2025, 2, 15), date(2025, 3, 30)]
    c, p = determine_stream_cadence(dates)
    # Irregular cadence does not qualify as regular stream
    assert c in [None, 'irregular']
