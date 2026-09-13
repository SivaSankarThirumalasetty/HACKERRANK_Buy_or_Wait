import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from src.evidence.messages import classify_message, MessageEvidence, MessageEffect, parse_message, apply_amendments_to_events
from src.models.domain import FinancialProfile, FinancialEvent, Request, PaymentOption, ForecastDay
from src.forecasting.cashflow import build_cashflow_forecast, is_balance_safe_throughout
from src.currency.converter import ExchangeRateTable
from src.affordability.engine import calculate_amount_safe_to_pay, find_earliest_safe_payment_date, make_decision
from src.payment_plans.generator import generate_full_payment_plan, generate_partial_payment_plan, generate_installment_plan

def test_messages_classification():
    scam = MessageEvidence('1', 'u', None, None, datetime.now(), 'x', 'pay the release charge')
    assert classify_message(scam) == MessageEffect.SCAM
    
    retry = MessageEvidence('2', 'u', None, None, datetime.now(), 'x', 'previous debit attempt failed')
    assert classify_message(retry) == MessageEffect.FAILED_DEBIT_RETRY
    
    val = MessageEvidence('3', 'u', None, None, datetime.now(), 'x', 'market value')
    assert classify_message(val) == MessageEffect.INVESTMENT_VALUATION
    
    ref = MessageEvidence('4', 'u', None, None, datetime.now(), 'x', 'refund has been initiated')
    assert classify_message(ref) == MessageEffect.REFUND_PENDING
    
    trans = MessageEvidence('5', 'u', None, None, datetime.now(), 'x', 'matching debit and credit same account')
    assert classify_message(trans) == MessageEffect.INTER_ACCOUNT_TRANSFER
    
    rent = MessageEvidence('6', 'u', None, None, datetime.now(), 'x', 'renewed lease increases')
    assert classify_message(rent) == MessageEffect.RENT_INCREASE_12PCT

def test_minimum_balance_violation():
    profile = FinancialProfile('u1', 'INR', Decimal('5000'), Decimal('2000'), [], [], [], [], ['full_payment'], None)
    fx = ExchangeRateTable([])
    forecast = build_cashflow_forecast(profile, [], date(2026, 1, 1), fx)
    # Asking for 4000 would leave 1000, but min balance is 2000 => safe amount is 3000
    safe_amt = calculate_amount_safe_to_pay(profile, forecast, date(2026, 1, 1), Decimal('4000'))
    assert safe_amt == Decimal('3000.00')

def test_request_deadline_violation_partial_payment():
    profile = FinancialProfile('u1', 'INR', Decimal('5000'), Decimal('1000'), [], [], [], [], ['partial_payment'], None)
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('1000'), 'INR', date(2026, 1, 15), True, 'test')
    forecast = [ForecastDay(date(2026, 1, 20), Decimal('10000'), Decimal('0'), Decimal('0'), Decimal('10000'), [])]
    # Earliest date for full payment is after desired_completion_date (2026-01-20 > 2026-01-15)
    plan = generate_partial_payment_plan(req, profile, Decimal('400'), date(2026, 1, 20), forecast)
    assert plan is None

def test_rent_increase_amendment():
    profile = FinancialProfile('u1', 'INR', Decimal('10000'), Decimal('1000'), [], [], [], [], [], None)
    ev = FinancialEvent('e1', 'u1', date(2026, 1, 10), date(2026, 1, 10), 'expense', 'rent', Decimal('2000'), 'INR', 'debit', 'scheduled', 'fixed', 'rent', None)
    msg = MessageEvidence('m1', 'u1', None, None, datetime.now(), 'service_provider', 'renewed lease increases')
    am = parse_message(msg)
    amended = apply_amendments_to_events([ev], [am], profile, date(2026, 1, 1), date(2026, 4, 1))
    assert amended[0].amount == Decimal('2240.00')

def test_no_safe_plan():
    profile = FinancialProfile('u1', 'INR', Decimal('1000'), Decimal('1000'), [], [], [], [], ['full_payment'], None)
    fx = ExchangeRateTable([])
    req = Request('r1', 'u1', date(2026, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2026, 1, 10), False, 'test')
    opt = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2026, 1, 1))
    
    decision, trace = make_decision(req, profile, [], [opt], fx)
    assert decision.amount_safe_to_pay == Decimal('0')
    assert decision.earliest_date_for_full_payment is None
    assert decision.affordability_status == 'not_affordable'
    assert decision.recommended_payment_method == 'not_recommended'
