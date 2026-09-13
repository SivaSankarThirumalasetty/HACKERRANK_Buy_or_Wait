from decimal import Decimal
from datetime import date, timedelta
from typing import List, Tuple, Optional, Set
from src.models.domain import PaymentOption, FinancialProfile, Request, PaymentPlan

def validate_installment_schedule(
    option: PaymentOption,
    payments: List[Tuple[date, Decimal]],
    profile: Optional[FinancialProfile] = None,
    request: Optional[Request] = None,
    expected_option_id: Optional[str] = None,
    completion_date: Optional[date] = None,
    financing_fee: Optional[Decimal] = None,
    available_option_ids: Optional[Set[str]] = None
) -> List[str]:
    """
    Validates that an installment payment schedule exactly matches the supplied payment option
    across all 11 contest specification dimensions:
    1. payment_option_id exists and matches
    2. payment method is installments
    3. number_of_payments exactly matches
    4. first_payment_date exactly matches
    5. every payment date exactly matches the option frequency
    6. every payment amount exactly matches payment_amount
    7. total payable exactly matches total_payable_amount
    8. financing fee is correctly represented
    9. completion date matches the final payment
    10. plan is within user's max_installment_months
    11. plan is accepted by user's payment preferences

    Returns a list of error strings; an empty list indicates the plan is valid.
    """
    errors: List[str] = []

    # 1. payment_option_id exists
    if not option.payment_option_id or not option.payment_option_id.strip():
        errors.append("Validation Error (Rule 1): Missing payment_option_id in supplied option.")
    elif available_option_ids is not None and option.payment_option_id not in available_option_ids:
        errors.append(f"Validation Error (Rule 1): Option ID '{option.payment_option_id}' does not exist in available options.")
    if expected_option_id is not None and option.payment_option_id != expected_option_id:
        errors.append(f"Validation Error (Rule 1): Plan option ID '{expected_option_id}' does not match option ID '{option.payment_option_id}'.")

    # 2. payment method is installments
    if option.payment_method != 'installments':
        errors.append(f"Validation Error (Rule 2): Payment method is '{option.payment_method}', expected 'installments'.")

    # 3. number_of_payments exactly matches
    if len(payments) != option.number_of_payments:
        errors.append(f"Validation Error (Rule 3): Number of payments {len(payments)} does not match option expected {option.number_of_payments}.")

    if not payments:
        errors.append("Validation Error: Payment schedule is empty.")
        return errors

    # 4. first_payment_date exactly matches
    first_date = payments[0][0]
    if first_date != option.first_payment_date:
        errors.append(f"Validation Error (Rule 4): First payment date {first_date} does not match option first_payment_date {option.first_payment_date}.")

    # 5. every payment date exactly matches the option frequency
    freq = option.payment_frequency_days if option.payment_frequency_days is not None else 30
    for idx, (p_date, _) in enumerate(payments):
        expected_date = option.first_payment_date + timedelta(days=idx * freq)
        if p_date != expected_date:
            errors.append(f"Validation Error (Rule 5): Payment {idx + 1} date {p_date} does not match expected date {expected_date} based on frequency of {freq} days.")

    # 6. every payment amount exactly matches payment_amount
    for idx, (_, p_amt) in enumerate(payments):
        if p_amt != option.payment_amount:
            errors.append(f"Validation Error (Rule 6): Payment {idx + 1} amount {p_amt} does not match option payment_amount {option.payment_amount}.")

    # 7. total payable exactly matches total_payable_amount
    total_paid = sum(amt for _, amt in payments)
    if total_paid != option.total_payable_amount:
        errors.append(f"Validation Error (Rule 7): Total payable sum {total_paid} does not match option total_payable_amount {option.total_payable_amount}.")

    # 8. financing fee is correctly represented
    if option.financing_fee < Decimal('0'):
        errors.append(f"Validation Error (Rule 8): Negative financing fee {option.financing_fee} in option.")
    if request is not None:
        expected_fee = option.total_payable_amount - request.requested_amount
        if option.financing_fee != expected_fee:
            errors.append(f"Validation Error (Rule 8): Financing fee {option.financing_fee} does not match total payable minus requested amount ({expected_fee}).")
    if financing_fee is not None and financing_fee != option.financing_fee:
        errors.append(f"Validation Error (Rule 8): Plan financing fee {financing_fee} does not match option financing fee {option.financing_fee}.")

    # 9. completion date matches the final payment
    final_payment_date = payments[-1][0]
    if completion_date is not None and completion_date != final_payment_date:
        errors.append(f"Validation Error (Rule 9): Completion date {completion_date} does not match final payment date {final_payment_date}.")

    # 10. plan is within user's max_installment_months
    if profile is not None:
        if profile.max_installment_months is None:
            errors.append("Validation Error (Rule 10): User does not permit installments (max_installment_months is None).")
        elif option.number_of_payments > profile.max_installment_months:
            errors.append(f"Validation Error (Rule 10): Number of payments {option.number_of_payments} exceeds user's max_installment_months {profile.max_installment_months}.")

    # 11. plan is accepted by user's payment preferences
    if profile is not None:
        if 'installments' not in profile.payment_methods:
            errors.append(f"Validation Error (Rule 11): 'installments' is not accepted by user's payment preferences {profile.payment_methods}.")

    return errors

def validate_installment_plan(
    plan: PaymentPlan,
    option: PaymentOption,
    profile: Optional[FinancialProfile] = None,
    request: Optional[Request] = None,
    available_option_ids: Optional[Set[str]] = None
) -> List[str]:
    """
    Validates a PaymentPlan object against a PaymentOption across all 11 criteria.
    """
    if plan.plan_type != 'installments':
        return [f"Validation Error (Rule 2): Plan type is '{plan.plan_type}', expected 'installments'."]

    return validate_installment_schedule(
        option=option,
        payments=plan.payments,
        profile=profile,
        request=request,
        expected_option_id=plan.option_id,
        completion_date=plan.completion_date,
        financing_fee=plan.financing_fee,
        available_option_ids=available_option_ids
    )
