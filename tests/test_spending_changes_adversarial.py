import pytest
from decimal import Decimal
from datetime import date, timedelta
from src.models.domain import FinancialProfile, FinancialEvent, Request, PaymentOption
from src.currency.converter import ExchangeRateTable
from src.affordability.engine import make_decision

def create_base_profile(
    user_id: str = 'u_adv',
    balance: Decimal = Decimal('1000.00'),
    min_balance: Decimal = Decimal('200.00'),
    categories_to_stop: list = None,
    categories_to_reduce: list = None,
    categories_to_protect: list = None
) -> FinancialProfile:
    return FinancialProfile(
        user_id=user_id,
        home_currency='USD',
        current_available_balance=balance,
        minimum_balance_to_keep=min_balance,
        financial_priorities=['debt_reduction'],
        expense_categories_to_protect=categories_to_protect or [],
        expense_categories_to_reduce=categories_to_reduce or [],
        expense_categories_to_stop=categories_to_stop or [],
        payment_methods=['full_payment', 'installments'],
        max_installment_months=6
    )

def create_dummy_fx():
    return ExchangeRateTable([])

def test_10_percent_reduction_is_enough_not_50_percent():
    """
    Test 1: Proves that when a 10% reduction of a flexible recurring expense
    is sufficient to make the plan safe, the optimizer reduces by 10% (100 -> 90),
    and NEVER applies an arbitrary 50% reduction (which would be 50).
    """
    req_date = date(2026, 5, 1)
    # Balanced salary of 100.00 settling monthly
    inc1 = FinancialEvent('inc_1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'income', 'salary', Decimal('100.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)
    inc2 = FinancialEvent('inc_2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'income', 'salary', Decimal('100.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)

    # Recurring flexible expense of 100.00
    ev1 = FinancialEvent('ev_d1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None)
    ev2 = FinancialEvent('ev_d2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None)

    # Balance 1000, Min balance 200, Payment 810 -> Deficit is 200 - (1000 - 810) = 10.00 (exactly 10% of 100)
    prof = create_base_profile(balance=Decimal('1000.00'), min_balance=Decimal('200.00'), categories_to_reduce=['dining'])
    req = Request('r1', 'u_adv', req_date, 'purchase', Decimal('810.00'), 'USD', req_date, False, 'Buy item')
    opt = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('810.00'), None, Decimal('0'), Decimal('810.00'), req_date)

    dec, trace = make_decision(req, prof, [inc1, inc2, ev1, ev2], [opt], create_dummy_fx())

    assert dec.affordability_status == 'affordable_with_plan'
    assert dec.recommended_payment_method == 'full_payment'
    # Must reduce by 10% (new amount = 90), never by 50%
    assert dec.spending_changes_needed == 'reduce_to:ev_d2:90'
    assert '50' not in dec.spending_changes_needed

def test_exact_37_25_reduction():
    """
    Test 2: Proves that when an exact fractional reduction of 37.25 is required
    to make the plan safe, the optimizer reduces the expense from 100.00 to exactly 62.75.
    """
    req_date = date(2026, 5, 1)
    inc1 = FinancialEvent('inc_1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'income', 'salary', Decimal('100.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)
    inc2 = FinancialEvent('inc_2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'income', 'salary', Decimal('100.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)

    ev1 = FinancialEvent('ev_d1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None)
    ev2 = FinancialEvent('ev_d2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None)

    # Balance 1000, Min balance 200, Payment 837.25 -> Deficit is 200 - (1000 - 837.25) = 37.25
    prof = create_base_profile(balance=Decimal('1000.00'), min_balance=Decimal('200.00'), categories_to_reduce=['dining'])
    req = Request('r2', 'u_adv', req_date, 'purchase', Decimal('837.25'), 'USD', req_date, False, 'Buy item')
    opt = PaymentOption('opt_1', 'r2', 'full_payment', 1, Decimal('837.25'), None, Decimal('0'), Decimal('837.25'), req_date)

    dec, trace = make_decision(req, prof, [inc1, inc2, ev1, ev2], [opt], create_dummy_fx())

    assert dec.affordability_status == 'affordable_with_plan'
    assert dec.recommended_payment_method == 'full_payment'
    # Exact reduction by 37.25 leaves 62.75
    assert dec.spending_changes_needed == 'reduce_to:ev_d2:62.75'

def test_stopping_better_than_reducing_when_appropriate():
    """
    Test 3: Proves that when stopping an affordable subscription (15.00) bridges
    the deficit, while reducing a different expense cannot reach 15.00 due to its minimum_allowed_amount,
    stopping is deterministically chosen.
    """
    req_date = date(2026, 5, 1)
    inc1 = FinancialEvent('inc_1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'income', 'salary', Decimal('115.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)
    inc2 = FinancialEvent('inc_2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'income', 'salary', Decimal('115.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)

    # Stream A: Stoppable subscription of 15.00
    ev_s1 = FinancialEvent('ev_s1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'subscription', 'streaming', Decimal('15.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)
    ev_s2 = FinancialEvent('ev_s2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'subscription', 'streaming', Decimal('15.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)

    # Stream B: Reducible expense of 100.00, but minimum_allowed_amount is 90.00 (max reduction 10.00 < 15.00 deficit!)
    ev_d1 = FinancialEvent('ev_d1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None, minimum_allowed_amount=Decimal('90.00'))
    ev_d2 = FinancialEvent('ev_d2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None, minimum_allowed_amount=Decimal('90.00'))

    prof = create_base_profile(balance=Decimal('1000.00'), min_balance=Decimal('200.00'), categories_to_stop=['streaming'], categories_to_reduce=['dining'])
    req = Request('r3', 'u_adv', req_date, 'purchase', Decimal('815.00'), 'USD', req_date, False, 'Buy item')
    opt = PaymentOption('opt_1', 'r3', 'full_payment', 1, Decimal('815.00'), None, Decimal('0'), Decimal('815.00'), req_date)

    dec, trace = make_decision(req, prof, [inc1, inc2, ev_s1, ev_s2, ev_d1, ev_d2], [opt], create_dummy_fx())

    assert dec.affordability_status == 'affordable_with_plan'
    assert dec.recommended_payment_method == 'full_payment'
    assert dec.spending_changes_needed == 'stop:ev_s2'

def test_multiple_events_required_when_single_event_insufficient():
    """
    Test 4: Proves that when a single event reduction is insufficient to cover the shortfall,
    the optimizer deterministically selects a multi-event combination.
    """
    req_date = date(2026, 5, 1)
    # Total deficit is 35.00:
    # Stream 1 (streaming stop) provides 15.00.
    # Stream 2 (dining reduce) provides up to 25.00 (from 100.00 down to minimum 75.00).
    # Neither alone can cover 35.00. Together, they cover 15.00 + 20.00 = 35.00.
    inc1 = FinancialEvent('inc_1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'income', 'salary', Decimal('115.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)
    inc2 = FinancialEvent('inc_2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'income', 'salary', Decimal('115.00'), 'USD', 'credit', 'settled', 'fixed', 'salary', None)

    ev_s1 = FinancialEvent('ev_s1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'subscription', 'streaming', Decimal('15.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)
    ev_s2 = FinancialEvent('ev_s2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'subscription', 'streaming', Decimal('15.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)

    ev_d1 = FinancialEvent('ev_d1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None, minimum_allowed_amount=Decimal('75.00'))
    ev_d2 = FinancialEvent('ev_d2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'dining', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'dining', None, minimum_allowed_amount=Decimal('75.00'))

    prof = create_base_profile(balance=Decimal('1000.00'), min_balance=Decimal('200.00'), categories_to_stop=['streaming'], categories_to_reduce=['dining'])
    req = Request('r4', 'u_adv', req_date, 'purchase', Decimal('835.00'), 'USD', req_date, False, 'Buy item')
    opt = PaymentOption('opt_1', 'r4', 'full_payment', 1, Decimal('835.00'), None, Decimal('0'), Decimal('835.00'), req_date)

    dec, trace = make_decision(req, prof, [inc1, inc2, ev_s1, ev_s2, ev_d1, ev_d2], [opt], create_dummy_fx())

    assert dec.affordability_status == 'affordable_with_plan'
    assert dec.recommended_payment_method == 'full_payment'
    assert dec.spending_changes_needed == 'stop:ev_s2|reduce_to:ev_d2:80'

def test_no_combination_sufficient_remains_not_affordable():
    """
    Test 5: Proves that when the required shortfall exceeds all possible spending reductions,
    no spending changes are recommended and the request remains not_affordable / not_recommended.
    """
    req_date = date(2026, 5, 1)
    prof = create_base_profile(
        balance=Decimal('1000.00'),
        min_balance=Decimal('200.00'),
        categories_to_stop=['streaming'],
        categories_to_reduce=['dining']
    )
    req = Request(
        request_id='r_test5',
        user_id='u_adv',
        request_date=req_date,
        request_type='purchase',
        requested_amount=Decimal('1300.00'),  # Exceeds total available balance + all possible reductions
        currency='USD',
        desired_completion_date=req_date,
        allows_partial_payment=False,
        request_text='Buy item'
    )
    ev_s1 = FinancialEvent('ev_s1', 'u_adv', date(2026, 3, 1), date(2026, 3, 1), 'subscription', 'streaming', Decimal('25.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)
    ev_s2 = FinancialEvent('ev_s2', 'u_adv', date(2026, 4, 1), date(2026, 4, 1), 'subscription', 'streaming', Decimal('25.00'), 'USD', 'debit', 'settled', 'stoppable', 'streaming', None)

    opt = PaymentOption('opt_1', 'r_test5', 'full_payment', 1, Decimal('1300.00'), None, Decimal('0'), Decimal('1300.00'), req_date)

    dec, trace = make_decision(req, prof, [ev_s1, ev_s2], [opt], create_dummy_fx())

    assert dec.affordability_status == 'not_affordable'
    assert dec.recommended_payment_method == 'not_recommended'
    assert dec.spending_changes_needed == 'none'
