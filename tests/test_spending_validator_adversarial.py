import pytest
from decimal import Decimal
from datetime import date
from src.models.domain import Decision, Request, FinancialProfile, PaymentOption, FinancialEvent
from src.validation.output_validator import validate_all_decisions

@pytest.fixture
def setup_spending_data():
    req_date = date(2026, 5, 1)
    req = Request(
        request_id='r_test',
        user_id='user_adv',
        request_date=req_date,
        request_type='purchase',
        requested_amount=Decimal('500.00'),
        currency='USD',
        desired_completion_date=req_date,
        allows_partial_payment=False,
        request_text='Test purchase'
    )
    prof = FinancialProfile(
        user_id='user_adv',
        home_currency='USD',
        current_available_balance=Decimal('1000.00'),
        minimum_balance_to_keep=Decimal('200.00'),
        financial_priorities=[],
        expense_categories_to_protect=['groceries'],
        expense_categories_to_reduce=['entertainment'],
        expense_categories_to_stop=['subscriptions'],
        payment_methods=['full_payment'],
        max_installment_months=None
    )
    ev_ent1 = FinancialEvent('ev_ent1', 'user_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'games', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'entertainment', None, minimum_allowed_amount=Decimal('20.00'))
    ev_ent2 = FinancialEvent('ev_ent2', 'user_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'games', Decimal('100.00'), 'USD', 'debit', 'settled', 'reducible', 'entertainment', None, minimum_allowed_amount=Decimal('20.00'))

    ev_sub1 = FinancialEvent('ev_sub1', 'user_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'stream', Decimal('50.00'), 'USD', 'debit', 'settled', 'stoppable', 'subscriptions', None)
    ev_sub2 = FinancialEvent('ev_sub2', 'user_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'stream', Decimal('50.00'), 'USD', 'debit', 'settled', 'stoppable', 'subscriptions', None)

    ev_groc1 = FinancialEvent('ev_groc1', 'user_adv', date(2026, 3, 1), date(2026, 3, 1), 'expense', 'food', Decimal('200.00'), 'USD', 'debit', 'settled', 'reducible', 'groceries', None)
    ev_groc2 = FinancialEvent('ev_groc2', 'user_adv', date(2026, 4, 1), date(2026, 4, 1), 'expense', 'food', Decimal('200.00'), 'USD', 'debit', 'settled', 'reducible', 'groceries', None)

    # One-time non-recurring expense (category 'shopping')
    ev_onetime = FinancialEvent('ev_one', 'user_adv', date(2026, 4, 15), date(2026, 4, 15), 'expense', 'shoes', Decimal('80.00'), 'USD', 'debit', 'settled', 'reducible', 'shopping', None)

    events = [ev_ent1, ev_ent2, ev_sub1, ev_sub2, ev_groc1, ev_groc2, ev_onetime]
    opts = [PaymentOption('opt_1', 'r_test', 'full_payment', 1, Decimal('500.00'), None, Decimal('0'), Decimal('500.00'), req_date)]

    return req, prof, events, opts

def test_spending_validator_passes_valid_changes(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_ent2:50.00|stop:ev_sub2',
        decision_explanation='Valid plan with spending changes.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert errors == []

def test_adversarial_protected_event_referenced(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_groc2:150.00',
        decision_explanation='Reduced protected groceries.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('protected' in e for e in errors)

def test_adversarial_non_recurring_event_referenced(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_one:40.00',
        decision_explanation='Reduced one-time shoes.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('not a recurring event' in e for e in errors)

def test_adversarial_stop_on_category_user_will_not_stop(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='stop:ev_ent2',
        decision_explanation='Stopped entertainment which user will not stop.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('not in user expense_categories_to_stop' in e for e in errors)

def test_adversarial_reduce_on_category_user_will_not_reduce(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_sub2:25.00',
        decision_explanation='Reduced subscriptions which user will not reduce.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('not in user expense_categories_to_reduce' in e for e in errors)

def test_adversarial_new_amount_greater_than_original(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_ent2:120.00',
        decision_explanation='Increased expense instead of reducing.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('strictly less than original amount' in e for e in errors)

def test_adversarial_new_amount_violates_minimum_allowed(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_ent2:15.00',
        decision_explanation='Reduced below minimum allowed floor.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('below event minimum_allowed_amount' in e for e in errors)

def test_adversarial_same_event_appears_twice(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='reduce_to:ev_ent2:60.00|reduce_to:ev_ent2:40.00',
        decision_explanation='Duplicate event in changes.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('appears more than once' in e for e in errors)

def test_adversarial_stop_and_reduce_target_same_event(setup_spending_data):
    req, prof, events, opts = setup_spending_data
    dec = Decision(
        request_id='r_test',
        amount_safe_to_pay=Decimal('500.00'),
        affordability_status='affordable_with_plan',
        recommended_payment_method='full_payment',
        payment_plan=f'{req.request_date}:500.00',
        earliest_date_for_full_payment=req.request_date,
        spending_changes_needed='stop:ev_ent2|reduce_to:ev_ent2:50.00',
        decision_explanation='Stop and reduce on same event.'
    )
    errors = validate_all_decisions([dec], [req], {prof.user_id: prof}, {req.request_id: opts}, events)
    assert any('appears more than once' in e for e in errors)
