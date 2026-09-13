import pytest
from decimal import Decimal
from datetime import date
from src.data.loaders import load_all, load_requests
from src.normalization.events import normalize_events
from src.currency.converter import ExchangeRateTable
from src.evidence.messages import parse_message
from src.forecasting.cashflow import build_cashflow_forecast
from src.affordability.engine import calculate_amount_safe_to_pay, make_decision
from tests.fixtures.reference_calculator import calculate_reference_amount_safe_to_pay

@pytest.fixture(scope='session')
def loaded_dataset():
    dataset_dir = 'dataset'
    profiles, events, _, payment_opts, messages, rates = load_all(dataset_dir)
    norm_events = normalize_events(events)
    fx_table = ExchangeRateTable(rates)
    eval_requests = load_requests(dataset_dir, 'requests.csv')
    sample_requests = load_requests(dataset_dir, 'sample_requests.csv')

    user_events = {}
    for ev in norm_events:
        user_events.setdefault(ev.user_id, []).append(ev)

    user_amendments = {}
    for m in messages:
        am = parse_message(m)
        user_amendments.setdefault(m.user_id, []).append(am)

    return {
        'profiles': profiles,
        'eval_requests': eval_requests,
        'sample_requests': sample_requests,
        'user_events': user_events,
        'user_amendments': user_amendments,
        'payment_opts': payment_opts,
        'fx_table': fx_table
    }

def test_mathematical_amount_safe_to_pay_evaluation_requests(loaded_dataset):
    d = loaded_dataset
    for req in d['eval_requests']:
        prof = d['profiles'][req.user_id]
        events = d['user_events'].get(req.user_id, [])
        amends = d['user_amendments'].get(req.user_id, [])
        opts = d['payment_opts'].get(req.request_id, [])

        # Reference calculator
        ref_safe, ref_diag = calculate_reference_amount_safe_to_pay(req, prof, events, d['fx_table'], amends)

        # Production forecast & calculate_amount_safe_to_pay
        prod_forecast = build_cashflow_forecast(prof, events, req.request_date, d['fx_table'], amends)
        prod_safe = calculate_amount_safe_to_pay(prof, prod_forecast, req.request_date, req.requested_amount)

        # Production engine make_decision
        dec, _ = make_decision(req, prof, events, opts, d['fx_table'], amends)

        assert ref_safe == prod_safe, f'Mismatch between reference and production for {req.request_id}: {ref_safe} vs {prod_safe}'
        assert prod_safe == dec.amount_safe_to_pay, f'Mismatch with engine decision for {req.request_id}: {prod_safe} vs {dec.amount_safe_to_pay}'

        # Mathematical property check
        assert Decimal('0') <= prod_safe <= req.requested_amount
        if prod_safe > Decimal('0'):
            for f in prod_forecast:
                if f.day >= req.request_date:
                    assert f.closing_balance - prod_safe >= prof.minimum_balance_to_keep - Decimal('0.001'), f"Payment {prod_safe} breaches minimum balance on {f.day} for {req.request_id}"
        else:
            # When prod_safe == 0, there must be at least one day where closing_balance < minimum_balance_to_keep (or margin < 0)
            has_deficit = any(f.closing_balance < prof.minimum_balance_to_keep for f in prod_forecast if f.day >= req.request_date)
            assert has_deficit, f"prod_safe is 0 but forecast never breaches minimum balance for {req.request_id}"

def test_mathematical_amount_safe_to_pay_sample_requests(loaded_dataset):
    d = loaded_dataset
    for req in d['sample_requests']:
        prof = d['profiles'][req.user_id]
        events = d['user_events'].get(req.user_id, [])
        amends = d['user_amendments'].get(req.user_id, [])
        opts = d['payment_opts'].get(req.request_id, [])

        ref_safe, _ = calculate_reference_amount_safe_to_pay(req, prof, events, d['fx_table'], amends)
        prod_forecast = build_cashflow_forecast(prof, events, req.request_date, d['fx_table'], amends)
        prod_safe = calculate_amount_safe_to_pay(prof, prod_forecast, req.request_date, req.requested_amount)
        dec, _ = make_decision(req, prof, events, opts, d['fx_table'], amends)

        assert ref_safe == prod_safe == dec.amount_safe_to_pay
