import pytest
import json
from datetime import date
from decimal import Decimal
from src.models.domain import Request, FinancialProfile, PaymentOption, FinancialEvent
from src.currency.converter import ExchangeRateTable
from src.affordability.engine import make_decision
from src.explainability.trace import DecisionTrace, PlanEvaluation, SafetyCheckResult
from src.explainability.generator import generate_concise_explanation

@pytest.fixture
def base_profile():
    return FinancialProfile(
        user_id='u1',
        home_currency='INR',
        current_available_balance=Decimal('10000'),
        minimum_balance_to_keep=Decimal('2000'),
        financial_priorities=['emergency_fund'],
        expense_categories_to_protect=['groceries', 'utilities'],
        expense_categories_to_reduce=['entertainment'],
        expense_categories_to_stop=['subscriptions'],
        payment_methods=['full_payment', 'partial_payment', 'installments'],
        max_installment_months=6
    )

def test_explainability_trace_fields_and_json(base_profile):
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), True, 'test request')
    opt = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])

    decision, trace = make_decision(req, base_profile, [], [opt], fx)

    # Check internal trace attributes
    assert trace.request_id == 'r1'
    assert trace.user_id == 'u1'
    assert trace.requested_amount == Decimal('5000')
    assert trace.starting_balance == Decimal('10000')
    assert trace.minimum_required_balance == Decimal('2000')
    assert len(trace.evaluated_plans) >= 1
    assert trace.selected_plan is not None
    assert trace.selected_plan['plan_type'] == 'full_payment'
    assert trace.concise_user_explanation != ""

    # Test JSON serialization
    trace_json = trace.to_json()
    assert isinstance(trace_json, str)
    data = json.loads(trace_json)
    assert data['request_id'] == 'r1'
    assert data['requested_amount'] == '5000'
    assert data['starting_balance'] == '10000'
    assert data['selected_plan']['plan_type'] == 'full_payment'

def test_explainability_rejected_plan_trace(base_profile):
    base_profile.current_available_balance = Decimal('2000')  # only 0 safe above minimum 2000
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'INR', date(2025, 1, 10), False, 'test request')
    opt = PaymentOption('opt_1', 'r1', 'full_payment', 1, Decimal('5000'), None, Decimal('0'), Decimal('5000'), date(2025, 1, 1))
    fx = ExchangeRateTable([])

    decision, trace = make_decision(req, base_profile, [], [opt], fx)
    assert decision.affordability_status == 'not_affordable'
    assert decision.recommended_payment_method == 'not_recommended'
    assert trace.selected_plan is None

    # Check rejection was recorded
    assert len(trace.evaluated_plans) >= 1
    rejected = [p for p in trace.evaluated_plans if not p.is_safe]
    assert len(rejected) >= 1
    assert "Insufficient balance" in rejected[0].rejection_reason

    # Verify concise explanation style
    assert "Do not proceed" in decision.decision_explanation or "Not safe" in decision.decision_explanation
    assert "INR 2000 minimum" in decision.decision_explanation

def test_generate_concise_explanation_custom():
    req = Request('r1', 'u1', date(2025, 1, 1), 'purchase', Decimal('5000'), 'EUR', date(2025, 1, 10), True, '')
    prof = FinancialProfile('u1', 'EUR', Decimal('1000'), Decimal('800'), [], [], [], [], ['full_payment'], None)
    
    # Violation explanation
    sc = SafetyCheckResult(is_safe=False, violation_date=date(2025, 1, 3), projected_balance=Decimal('200'), minimum_required=Decimal('800'), deficit=Decimal('600'))
    expl = generate_concise_explanation(req, prof, None, None, safety_check=sc)
    assert "Not safe to pay the full amount today" in expl
    assert "2025-01-03" in expl
    assert "EUR 800 minimum" in expl
