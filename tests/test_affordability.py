import pytest
from datetime import date, timedelta
from decimal import Decimal
from src.models.domain import FinancialProfile, ForecastDay, Request, PaymentOption, FinancialEvent
from src.currency.converter import ExchangeRateTable
from src.affordability.engine import (
    calculate_amount_safe_to_pay,
    find_earliest_safe_payment_date,
    make_decision
)

@pytest.fixture
def base_profile():
    return FinancialProfile(
        user_id='u1',
        home_currency='INR',
        current_available_balance=Decimal('10000'),
        minimum_balance_to_keep=Decimal('1000'),
        financial_priorities=[],
        expense_categories_to_protect=[],
        expense_categories_to_reduce=[],
        expense_categories_to_stop=[],
        payment_methods=['full_payment', 'partial_payment', 'installments'],
        max_installment_months=12
    )

def test_afford_full(base_profile):
    forecast = [ForecastDay(date(2025, 1, 1) + timedelta(days=i), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), []) for i in range(90)]
    amt = calculate_amount_safe_to_pay(base_profile, forecast, date(2025, 1, 1), Decimal('5000'))
    assert amt == Decimal('5000.00')

def test_afford_nothing(base_profile):
    forecast = [ForecastDay(date(2025, 1, 1) + timedelta(days=i), Decimal('1500'), Decimal('0'), Decimal('0'), Decimal('1500'), []) for i in range(90)]
    amt = calculate_amount_safe_to_pay(base_profile, forecast, date(2025, 1, 1), Decimal('5000'))
    assert amt == Decimal('500.00')

def test_afford_partial(base_profile):
    forecast = [ForecastDay(date(2025, 1, 1) + timedelta(days=i), Decimal('4000'), Decimal('0'), Decimal('0'), Decimal('4000'), []) for i in range(90)]
    amt = calculate_amount_safe_to_pay(base_profile, forecast, date(2025, 1, 1), Decimal('5000'))
    assert amt == Decimal('3000.00')

def test_earliest_safe_date(base_profile):
    forecast = [
        ForecastDay(date(2025, 1, 1), Decimal('2000'), Decimal('0'), Decimal('0'), Decimal('2000'), []),
        ForecastDay(date(2025, 1, 2), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])
    ]
    d = find_earliest_safe_payment_date(base_profile, forecast, Decimal('5000'), date(2025, 1, 1), date(2025, 1, 2))
    assert d == date(2025, 1, 2)

def test_decision_affordable_now(base_profile):
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), True, 'test')
    opt = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])
    
    decision, trace = make_decision(req, base_profile, [], [opt], fx)
    assert decision.affordability_status == 'affordable_now'
    assert decision.recommended_payment_method == 'full_payment'
    assert decision.payment_plan == '2025-01-01:5000'
    assert decision.earliest_date_for_full_payment == date(2025, 1, 1)
    assert decision.spending_changes_needed == 'none'
    assert "Selected: full_payment" in trace.summary()

def test_decision_affordable_with_installments(base_profile):
    # Starting balance is 3000, minimum is 1000 => amount safe today is 2000, requested is 4000
    # Add scheduled income on 2025-01-20 so the second installment of 2000 is also safe
    base_profile.current_available_balance = Decimal('3000')
    base_profile.payment_methods = ['installments']
    inc_ev = FinancialEvent('e_inc2', 'u1', date(2025, 1, 20), date(2025, 1, 20), 'income', 'salary', Decimal('3000'), 'INR', 'credit', 'scheduled', 'fixed', 'salary', None)
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('4000'), 'INR', date(2025, 3, 10), False, 'test')
    opt_full = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('4000'), None, Decimal('0'), Decimal('4000'), date(2025, 1, 1))
    opt_inst = PaymentOption('opt_2', 'r1', 'installments', 2, Decimal('2000'), 30, Decimal('50'), Decimal('4050'), date(2025, 1, 1))
    fx = ExchangeRateTable([])
    
    decision, trace = make_decision(req, base_profile, [inc_ev], [opt_full, opt_inst], fx)
    assert decision.affordability_status == 'affordable_with_plan'
    assert decision.recommended_payment_method == 'installments'
    assert decision.payment_plan == '2025-01-01:2000|2025-01-31:2000'

def test_decision_affordable_with_partial_payment(base_profile):
    base_profile.current_available_balance = Decimal('4000')
    # Scheduled income of 5000 arriving on 2025-01-05
    inc_ev = FinancialEvent('e_inc', 'u1', date(2025, 1, 5), date(2025, 1, 5), 'income', 'bonus', Decimal('5000'), 'INR', 'credit', 'scheduled', 'fixed', 'salary', None)
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), True, 'test')
    opt_full = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])

    decision, trace = make_decision(req, base_profile, [inc_ev], [opt_full], fx)
    assert decision.affordability_status == 'affordable_with_plan'
    assert decision.recommended_payment_method == 'partial_payment'
    assert decision.amount_safe_to_pay == Decimal('3000.00')
    assert decision.payment_plan == '2025-01-01:3000|2025-01-05:2000'

def test_decision_affordable_later_wait(base_profile):
    base_profile.current_available_balance = Decimal('2000')  # only 1000 safe
    # User does NOT consider partial payment, only full payment
    base_profile.payment_methods = ['full_payment']
    inc_ev = FinancialEvent('e_inc', 'u1', date(2025, 1, 5), date(2025, 1, 5), 'income', 'bonus', Decimal('5000'), 'INR', 'credit', 'scheduled', 'fixed', 'salary', None)
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), False, 'test')
    opt_full = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])

    decision, trace = make_decision(req, base_profile, [inc_ev], [opt_full], fx)
    assert decision.affordability_status == 'affordable_later'
    assert decision.recommended_payment_method == 'wait'
    assert decision.payment_plan == '2025-01-05:5000'
    assert decision.earliest_date_for_full_payment == date(2025, 1, 5)

def test_decision_not_affordable(base_profile):
    base_profile.current_available_balance = Decimal('1000')  # at minimum
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), False, 'test')
    opt_full = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])

    decision, trace = make_decision(req, base_profile, [], [opt_full], fx)
    assert decision.affordability_status == 'not_affordable'
    assert decision.recommended_payment_method == 'not_recommended'
    assert decision.payment_plan == 'none'
    assert decision.spending_changes_needed == 'none'
