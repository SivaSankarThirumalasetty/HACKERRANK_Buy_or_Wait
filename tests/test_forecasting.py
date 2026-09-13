import pytest
from decimal import Decimal
from datetime import date
from src.models.domain import FinancialProfile, FinancialEvent
from src.forecasting.cashflow import build_cashflow_forecast, is_balance_safe_throughout
from src.currency.converter import ExchangeRateTable

@pytest.fixture
def base_profile():
    return FinancialProfile('u1', 'INR', Decimal('10000'), Decimal('1000'), [], [], [], [], [], None)

@pytest.fixture
def base_fx():
    return ExchangeRateTable([{'date': date(2025, 1, 1), 'from_currency': 'USD', 'to_currency': 'INR', 'rate': Decimal('80.0')}])

def test_simple_forecast(base_profile, base_fx):
    ev = FinancialEvent('1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('2000'), 'INR', 'debit', 'scheduled', 'x', 'x', None)
    forecast = build_cashflow_forecast(base_profile, [ev], date(2025, 1, 1), base_fx)
    
    assert forecast[0].opening_balance == Decimal('10000')
    assert forecast[0].closing_balance == Decimal('8000')
    assert forecast[1].opening_balance == Decimal('8000')

def test_pending_debit(base_profile, base_fx):
    ev = FinancialEvent('1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1000'), 'INR', 'debit', 'pending', 'x', 'x', None)
    forecast = build_cashflow_forecast(base_profile, [ev], date(2025, 1, 1), base_fx)
    assert forecast[0].opening_balance == Decimal('9000')

def test_fx_conversion(base_profile, base_fx):
    ev = FinancialEvent('1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('100'), 'USD', 'credit', 'scheduled', 'x', 'x', None)
    forecast = build_cashflow_forecast(base_profile, [ev], date(2025, 1, 1), base_fx)
    assert forecast[0].closing_balance == Decimal('18000')

def test_safety(base_profile, base_fx):
    ev = FinancialEvent('1', 'u1', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('9500'), 'INR', 'debit', 'scheduled', 'x', 'x', None)
    forecast = build_cashflow_forecast(base_profile, [ev], date(2025, 1, 1), base_fx)
    # closing day 0 is 500
    assert not is_balance_safe_throughout(forecast, base_profile.minimum_balance_to_keep, date(2025, 1, 1), date(2025, 1, 2))
