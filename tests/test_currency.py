import pytest
from decimal import Decimal
from datetime import date
from src.currency.converter import ExchangeRateTable

@pytest.fixture
def rates_data():
    return [
        {'date': date(2025, 1, 1), 'from_currency': 'USD', 'to_currency': 'INR', 'rate': Decimal('80.0')},
        {'date': date(2025, 1, 10), 'from_currency': 'USD', 'to_currency': 'INR', 'rate': Decimal('82.0')},
        {'date': date(2025, 1, 1), 'from_currency': 'EUR', 'to_currency': 'USD', 'rate': Decimal('1.1')},
        {'date': date(2025, 1, 1), 'from_currency': 'EUR', 'to_currency': 'ZAR', 'rate': Decimal('20.0')},
    ]

def test_same_currency(rates_data):
    table = ExchangeRateTable(rates_data)
    assert table.convert(Decimal('100'), 'USD', 'USD', date(2025, 1, 5)) == Decimal('100')

def test_direct_pair(rates_data):
    table = ExchangeRateTable(rates_data)
    assert table.convert(Decimal('100'), 'USD', 'INR', date(2025, 1, 5)) == Decimal('8000.0')
    assert table.convert(Decimal('100'), 'USD', 'INR', date(2025, 1, 15)) == Decimal('8200.0')

def test_inverse_pair(rates_data):
    table = ExchangeRateTable(rates_data)
    # INR -> USD via USD -> INR inverse. rate 80, inverse 1/80
    assert table.convert(Decimal('8000.0'), 'INR', 'USD', date(2025, 1, 5)) == Decimal('100')

def test_multi_hop(rates_data):
    table = ExchangeRateTable(rates_data)
    # ZAR -> INR via EUR -> USD -> INR
    # ZAR -> EUR = 1/20 = 0.05
    # EUR -> USD = 1.1
    # USD -> INR = 80
    # 100 ZAR = 100 * 0.05 * 1.1 * 80 = 440 INR
    assert table.convert(Decimal('100'), 'ZAR', 'INR', date(2025, 1, 5)) == Decimal('440.0')

def test_missing_rate(rates_data):
    table = ExchangeRateTable(rates_data)
    with pytest.raises(ValueError):
        table.convert(Decimal('100'), 'IDR', 'INR', date(2025, 1, 5))
