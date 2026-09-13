import pytest
from datetime import date, timedelta
from decimal import Decimal
from src.models.domain import PaymentOption, FinancialProfile, ForecastDay, Request, PaymentPlan
from src.payment_plans.generator import (
    generate_full_payment_plan,
    generate_partial_payment_plan,
    generate_installment_plan,
    generate_wait_plan,
    rank_candidate_plans,
    format_payment_plan
)
from src.explainability.trace import DecisionTrace

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

def test_full_plan_safe(base_profile):
    opt = PaymentOption('o1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    forecast = [ForecastDay(date(2025, 1, 1), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])]
    p = generate_full_payment_plan(opt, base_profile, forecast)
    assert p.is_safe is True
    assert p.total_amount == Decimal('5000')

def test_partial_plan_success(base_profile):
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), True, 'test')
    forecast = [
        ForecastDay(date(2025, 1, 1), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), []),
        ForecastDay(date(2025, 1, 5), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])
    ]
    p = generate_partial_payment_plan(req, base_profile, Decimal('2000'), date(2025, 1, 5), forecast)
    assert p is not None
    assert p.is_safe is True
    assert p.payments == [(date(2025, 1, 1), Decimal('2000')), (date(2025, 1, 5), Decimal('3000'))]
    assert p.total_amount == Decimal('5000')

def test_partial_plan_rejected_when_not_allowed(base_profile):
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), False, 'test')
    forecast = [ForecastDay(date(2025, 1, 1), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])]
    p = generate_partial_payment_plan(req, base_profile, Decimal('2000'), date(2025, 1, 5), forecast)
    assert p is None

def test_partial_plan_rejected_when_completion_exceeded(base_profile):
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), True, 'test')
    forecast = [ForecastDay(date(2025, 1, 15), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])]
    # earliest date is 2025-01-15, which is after desired_completion_date 2025-01-10
    p = generate_partial_payment_plan(req, base_profile, Decimal('2000'), date(2025, 1, 15), forecast)
    assert p is None

def test_installment_plan(base_profile):
    opt = PaymentOption('o1', 'r1', 'installments', 3, Decimal('1000'), 30, Decimal('50'), Decimal('3050'), date(2025, 1, 1))
    forecast = [
        ForecastDay(date(2025, 1, 1), Decimal('5000'), Decimal('0'), Decimal('0'), Decimal('5000'), []),
        ForecastDay(date(2025, 1, 31), Decimal('5000'), Decimal('0'), Decimal('0'), Decimal('5000'), []),
        ForecastDay(date(2025, 3, 2), Decimal('5000'), Decimal('0'), Decimal('0'), Decimal('5000'), [])
    ]
    p = generate_installment_plan(opt, base_profile, forecast)
    assert p is not None
    assert p.is_safe is True
    assert len(p.payments) == 3
    assert p.total_amount == Decimal('3050')

def test_installment_rejected_max_months(base_profile):
    base_profile.max_installment_months = 2
    opt = PaymentOption('o1', 'r1', 'installments', 3, Decimal('1000'), 30, Decimal('0'), Decimal('3000'), date(2025, 1, 1))
    p = generate_installment_plan(opt, base_profile, [])
    assert p is None

def test_installment_rejected_user_unwilling(base_profile):
    base_profile.payment_methods = ['full_payment']
    opt = PaymentOption('o1', 'r1', 'installments', 3, Decimal('1000'), 30, Decimal('0'), Decimal('3000'), date(2025, 1, 1))
    p = generate_installment_plan(opt, base_profile, [])
    assert p is None

def test_ranking_priority():
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('1000'), 'INR', date(2025, 1, 10), True, 'test')
    trace = DecisionTrace('r1', 'u1')

    # p1: late (completion 2025-01-15 > 2025-01-10)
    p1 = PaymentPlan('full_payment', [(date(2025, 1, 15), Decimal('1000'))], Decimal('1000'), Decimal('0'), 'opt_1', True, '', [], date(2025, 1, 15))
    # p2: on time, no changes, total 1050 (installments with fee)
    p2 = PaymentPlan('installments', [(date(2025, 1, 1), Decimal('525')), (date(2025, 1, 5), Decimal('525'))], Decimal('1050'), Decimal('50'), 'opt_2', True, '', [], date(2025, 1, 5))
    # p3: on time, with spending changes, total 1000
    p3 = PaymentPlan('full_payment', [(date(2025, 1, 1), Decimal('1000'))], Decimal('1000'), Decimal('0'), 'opt_3', True, '', ['stop:e1'], date(2025, 1, 1))
    # p4: on time, no changes, total 1000 (best!)
    p4 = PaymentPlan('full_payment', [(date(2025, 1, 1), Decimal('1000'))], Decimal('1000'), Decimal('0'), 'opt_4', True, '', [], date(2025, 1, 1))

    # Test 1: On-time vs late
    best = rank_candidate_plans([p1, p2], req, trace)
    assert best == p2

    # Test 2: No spending changes vs spending changes
    best2 = rank_candidate_plans([p2, p3], req, trace)
    assert best2 == p2

    # Test 3: Total amount comparison (p4=1000 vs p2=1050)
    best3 = rank_candidate_plans([p2, p4], req, trace)
    assert best3 == p4
    assert trace.selected_plan == p4

def test_format_plan():
    p = PaymentPlan('full_payment', [(date(2025, 1, 1), Decimal('1000'))], Decimal('1000'), Decimal('0'), 'o1', True, '')
    assert format_payment_plan(p) == '2025-01-01:1000'
    assert format_payment_plan(None) == 'none'

def test_adversarial_ranking_case_1_total_cost_beats_spending_reduction_when_both_have_changes():
    """
    Case 1:
    Plan A requires spending reduction 100 but costs 1000.
    Plan B requires spending reduction 200 but costs 800.
    Both are on time and both require changes.
    Expected: Plan B wins because total amount paid is lower.
    """
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('1000'), 'USD', date(2026, 1, 10), False, 'test')
    plan_a = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 1), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_1',
        is_safe=True,
        explanation='',
        spending_changes=['reduce_to:e1:100'],
        completion_date=date(2026, 1, 1),
        total_spending_reduction=Decimal('100')
    )
    plan_b = PaymentPlan(
        plan_type='installments',
        payments=[(date(2026, 1, 1), Decimal('400')), (date(2026, 1, 5), Decimal('400'))],
        total_amount=Decimal('800'),
        financing_fee=Decimal('0'),
        option_id='opt_2',
        is_safe=True,
        explanation='',
        spending_changes=['reduce_to:e2:200'],
        completion_date=date(2026, 1, 5),
        total_spending_reduction=Decimal('200')
    )

    best = rank_candidate_plans([plan_a, plan_b], req)
    assert best == plan_b

def test_adversarial_ranking_case_2_earlier_payment_wins():
    """
    Case 2:
    Two plans have identical total amount.
    Earlier payment wins.
    """
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('1000'), 'USD', date(2026, 1, 10), False, 'test')
    plan_early = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 2), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_early',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 2)
    )
    plan_late = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 5), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_late',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 5)
    )

    best = rank_candidate_plans([plan_late, plan_early], req)
    assert best == plan_early

def test_adversarial_ranking_case_3_fewer_payments_wins():
    """
    Case 3:
    Two plans have identical total amount and first payment date.
    Fewer payments wins.
    """
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('1000'), 'USD', date(2026, 1, 10), False, 'test')
    plan_fewer = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 1), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_1',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 1)
    )
    plan_more = PaymentPlan(
        plan_type='installments',
        payments=[(date(2026, 1, 1), Decimal('500')), (date(2026, 1, 5), Decimal('500'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_2',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 5)
    )

    best = rank_candidate_plans([plan_more, plan_fewer], req)
    assert best == plan_fewer

def test_adversarial_ranking_case_4_lowest_option_id_wins():
    """
    Case 4:
    Everything else identical.
    Lowest payment_option_id wins.
    """
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('1000'), 'USD', date(2026, 1, 10), False, 'test')
    plan_opt1 = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 1), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_10',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 1)
    )
    plan_opt2 = PaymentPlan(
        plan_type='full_payment',
        payments=[(date(2026, 1, 1), Decimal('1000'))],
        total_amount=Decimal('1000'),
        financing_fee=Decimal('0'),
        option_id='opt_20',
        is_safe=True,
        explanation='',
        spending_changes=[],
        completion_date=date(2026, 1, 1)
    )

    best = rank_candidate_plans([plan_opt2, plan_opt1], req)
    assert best == plan_opt1

