import pytest
from datetime import date
from decimal import Decimal
from src.models.domain import FinancialEvent
from src.normalization.events import normalize_events, get_cash_effective_events, detect_recurring_events

def test_ocr_amount():
    ev = FinancialEvent(
        event_id='event_253', user_id='u1', event_date=date(2025, 1, 1), settlement_date=date(2025, 1, 1),
        event_type='income', description='test', amount=None, currency='IDR',
        direction='credit', status='settled', flexibility='fixed', category='salary', linked_event_id=None
    )
    norm = normalize_events([ev])
    assert norm[0].amount == Decimal('4365000')

def test_cash_effective_events():
    ev1 = FinancialEvent('1', 'u', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1'), 'USD', 'credit', 'cancelled', 'x', 'x', None)
    ev2 = FinancialEvent('2', 'u', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1'), 'USD', 'credit', 'failed', 'x', 'x', None)
    ev3 = FinancialEvent('3', 'u', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1'), 'USD', 'non_cash', 'settled', 'x', 'x', None)
    ev4 = FinancialEvent('4', 'u', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1'), 'USD', 'debit', 'pending', 'x', 'x', None)
    ev5 = FinancialEvent('5', 'u', date(2025, 1, 1), date(2025, 1, 1), 'x', 'x', Decimal('1'), 'USD', 'credit', 'pending', 'x', 'x', None)
    
    eff = get_cash_effective_events([ev1, ev2, ev3, ev4, ev5])
    assert len(eff) == 1
    assert eff[0].event_id == '4'

def test_recurring_events():
    ev1 = FinancialEvent('1', 'u', date(2025, 1, 1), date(2025, 1, 1), 'expense', 'x', Decimal('1'), 'USD', 'debit', 'settled', 'x', 'rent', None)
    ev2 = FinancialEvent('2', 'u', date(2025, 1, 31), date(2025, 1, 31), 'expense', 'x', Decimal('1'), 'USD', 'debit', 'settled', 'x', 'rent', None)
    
    evs = detect_recurring_events([ev1, ev2], 'u', date(2025, 2, 1))
    assert all(e.is_recurring for e in evs)
    assert all(e.recurrence_period_days == 30 for e in evs)
    
    ev3 = FinancialEvent('3', 'u', date(2025, 1, 1), date(2025, 1, 1), 'expense', 'x', Decimal('1'), 'USD', 'debit', 'settled', 'x', 'food', None)
    evs2 = detect_recurring_events([ev3], 'u', date(2025, 2, 1))
    assert not evs2[0].is_recurring
