import pytest
from decimal import Decimal
from datetime import date, timedelta
from src.models.domain import PaymentOption, FinancialProfile, Request, PaymentPlan
from src.validation.installment_validator import validate_installment_schedule, validate_installment_plan

@pytest.fixture
def base_setup():
    opt = PaymentOption(
        payment_option_id='opt_inst_101',
        request_id='req_500',
        payment_method='installments',
        number_of_payments=3,
        payment_amount=Decimal('100.00'),
        payment_frequency_days=30,
        financing_fee=Decimal('15.00'),
        total_payable_amount=Decimal('300.00'),
        first_payment_date=date(2026, 4, 1)
    )
    req = Request(
        request_id='req_500',
        user_id='user_500',
        request_date=date(2026, 4, 1),
        request_type='purchase',
        requested_amount=Decimal('285.00'),  # 300.00 total - 285.00 = 15.00 fee
        currency='USD',
        desired_completion_date=date(2026, 6, 30),
        allows_partial_payment=False,
        request_text='Purchase item'
    )
    prof = FinancialProfile(
        user_id='user_500',
        home_currency='USD',
        current_available_balance=Decimal('1000.00'),
        minimum_balance_to_keep=Decimal('200.00'),
        financial_priorities=[],
        expense_categories_to_protect=[],
        expense_categories_to_reduce=[],
        expense_categories_to_stop=[],
        payment_methods=['installments', 'full_payment'],
        max_installment_months=6
    )
    # Valid schedule:
    # 1: 2026-04-01: 100.00
    # 2: 2026-05-01: 100.00 (+30d)
    # 3: 2026-05-31: 100.00 (+30d)
    valid_payments = [
        (date(2026, 4, 1), Decimal('100.00')),
        (date(2026, 5, 1), Decimal('100.00')),
        (date(2026, 5, 31), Decimal('100.00'))
    ]
    return opt, req, prof, valid_payments

def test_correct_option(base_setup):
    """
    Test 1: Correct option — perfectly matching schedule passes all 11 criteria without errors.
    """
    opt, req, prof, valid_payments = base_setup
    available_ids = {opt.payment_option_id, 'opt_inst_102'}
    
    # Validate schedule
    errors = validate_installment_schedule(
        option=opt,
        payments=valid_payments,
        profile=prof,
        request=req,
        expected_option_id='opt_inst_101',
        completion_date=date(2026, 5, 31),
        financing_fee=Decimal('15.00'),
        available_option_ids=available_ids
    )
    assert errors == [], f"Expected no errors for correct option, got: {errors}"

    # Validate PaymentPlan object
    plan = PaymentPlan(
        plan_type='installments',
        payments=valid_payments,
        total_amount=Decimal('300.00'),
        financing_fee=Decimal('15.00'),
        option_id='opt_inst_101',
        is_safe=True,
        explanation='Valid installment plan',
        completion_date=date(2026, 5, 31)
    )
    plan_errors = validate_installment_plan(
        plan=plan,
        option=opt,
        profile=prof,
        request=req,
        available_option_ids=available_ids
    )
    assert plan_errors == [], f"Expected no plan errors for correct option, got: {plan_errors}"

def test_wrong_first_date(base_setup):
    """
    Test 2: Wrong first date — schedule starts on 2026-04-05 instead of 2026-04-01.
    Must be rejected with first_payment_date mismatch.
    """
    opt, req, prof, valid_payments = base_setup
    bad_payments = [
        (date(2026, 4, 5), Decimal('100.00')),  # Wrong first date
        (date(2026, 5, 1), Decimal('100.00')),
        (date(2026, 5, 31), Decimal('100.00'))
    ]
    errors = validate_installment_schedule(
        option=opt,
        payments=bad_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("First payment date" in err or "Rule 4" in err for err in errors)

def test_wrong_second_date(base_setup):
    """
    Test 3: Wrong second date — first date matches, but second payment is 2026-05-10 instead of 2026-05-01.
    Must be rejected with frequency / payment date mismatch.
    """
    opt, req, prof, valid_payments = base_setup
    bad_payments = [
        (date(2026, 4, 1), Decimal('100.00')),
        (date(2026, 5, 10), Decimal('100.00')),  # Wrong second date (gap is 39 days, not 30)
        (date(2026, 5, 31), Decimal('100.00'))
    ]
    errors = validate_installment_schedule(
        option=opt,
        payments=bad_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("Payment 2 date" in err or "Rule 5" in err for err in errors)

def test_wrong_amount(base_setup):
    """
    Test 4: Wrong amount — second payment is 95.00 instead of 100.00.
    Must be rejected with payment amount mismatch.
    """
    opt, req, prof, valid_payments = base_setup
    bad_payments = [
        (date(2026, 4, 1), Decimal('100.00')),
        (date(2026, 5, 1), Decimal('95.00')),  # Wrong amount
        (date(2026, 5, 31), Decimal('100.00'))
    ]
    errors = validate_installment_schedule(
        option=opt,
        payments=bad_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("amount" in err or "Rule 6" in err for err in errors)

def test_wrong_payment_count(base_setup):
    """
    Test 5: Wrong payment count — schedule has 2 payments instead of 3.
    Must be rejected with number of payments mismatch.
    """
    opt, req, prof, valid_payments = base_setup
    bad_payments = [
        (date(2026, 4, 1), Decimal('100.00')),
        (date(2026, 5, 1), Decimal('100.00'))
        # Missing 3rd payment
    ]
    errors = validate_installment_schedule(
        option=opt,
        payments=bad_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("Number of payments" in err or "Rule 3" in err for err in errors)

def test_wrong_total(base_setup):
    """
    Test 6: Wrong total — sum of payments does not match option total_payable_amount.
    """
    opt, req, prof, valid_payments = base_setup
    # Create option with total 305.00 but payments sum to 300.00
    bad_opt = PaymentOption(
        payment_option_id='opt_inst_101',
        request_id='req_500',
        payment_method='installments',
        number_of_payments=3,
        payment_amount=Decimal('100.00'),
        payment_frequency_days=30,
        financing_fee=Decimal('20.00'),
        total_payable_amount=Decimal('305.00'),  # Mismatched total
        first_payment_date=date(2026, 4, 1)
    )
    errors = validate_installment_schedule(
        option=bad_opt,
        payments=valid_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("Total payable sum" in err or "Rule 7" in err for err in errors)

def test_wrong_option_id(base_setup):
    """
    Test 7: Wrong option ID — option ID is not in available options or does not match plan option ID.
    """
    opt, req, prof, valid_payments = base_setup
    # Case A: Plan claims to be from opt_inst_999
    errors = validate_installment_schedule(
        option=opt,
        payments=valid_payments,
        expected_option_id='opt_inst_999'
    )
    assert len(errors) > 0
    assert any("Plan option ID" in err or "Rule 1" in err for err in errors)

    # Case B: Option ID does not exist in available_option_ids
    errors_b = validate_installment_schedule(
        option=opt,
        payments=valid_payments,
        available_option_ids={'opt_other_1', 'opt_other_2'}
    )
    assert len(errors_b) > 0
    assert any("does not exist in available options" in err or "Rule 1" in err for err in errors_b)

def test_wrong_frequency(base_setup):
    """
    Test 8: Wrong frequency — option specifies 14 days, but schedule is spaced by 30 days.
    """
    opt, req, prof, valid_payments = base_setup
    biweekly_opt = PaymentOption(
        payment_option_id='opt_inst_101',
        request_id='req_500',
        payment_method='installments',
        number_of_payments=3,
        payment_amount=Decimal('100.00'),
        payment_frequency_days=14,  # Biweekly frequency
        financing_fee=Decimal('15.00'),
        total_payable_amount=Decimal('300.00'),
        first_payment_date=date(2026, 4, 1)
    )
    # Schedule dates are spaced by 30 days, not 14 days
    errors = validate_installment_schedule(
        option=biweekly_opt,
        payments=valid_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("based on frequency of 14 days" in err or "Rule 5" in err for err in errors)

def test_exceeds_max_installment_months(base_setup):
    """
    Test 9: Option exceeds user's max_installment_months.
    """
    opt, req, prof, valid_payments = base_setup
    prof.max_installment_months = 2  # User allows at most 2 payments
    errors = validate_installment_schedule(
        option=opt,  # Option has 3 payments
        payments=valid_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("exceeds user's max_installment_months" in err or "Rule 10" in err for err in errors)

def test_user_rejects_installments(base_setup):
    """
    Test 10: User does not accept installments in payment_methods.
    """
    opt, req, prof, valid_payments = base_setup
    prof.payment_methods = ['full_payment']  # User does not accept installments
    errors = validate_installment_schedule(
        option=opt,
        payments=valid_payments,
        profile=prof,
        request=req
    )
    assert len(errors) > 0
    assert any("not accepted by user's payment preferences" in err or "Rule 11" in err for err in errors)
