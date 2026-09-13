import pytest
from src.ui.app import app, DATA, DEMO_CONFIGS, STATUS_BADGE_MAP
from src.affordability.engine import make_decision

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_requests_dynamic_source_of_truth(client):
    res = client.get('/api/requests')
    assert res.status_code == 200
    data = res.get_json()
    assert 'demos' in data
    assert 'all_requests' in data
    assert len(data['demos']) == len(DEMO_CONFIGS)

    for demo in data['demos']:
        req_id = demo['id']
        req = DATA['requests'][req_id]
        prof = DATA['profiles'][req.user_id]
        events = DATA['user_events'].get(req.user_id, [])
        amends = DATA['user_amendments'].get(req.user_id, [])
        opts = DATA['payment_opts'].get(req_id, [])
        fx_table = DATA['fx_table']

        decision, _ = make_decision(
            request=req,
            profile=prof,
            events=events,
            payment_options=opts,
            fx_table=fx_table,
            amendments=amends
        )

        expected_badge_info = STATUS_BADGE_MAP[decision.affordability_status]

        assert demo['affordability_status'] == decision.affordability_status
        assert demo['recommended_payment_method'] == decision.recommended_payment_method
        assert demo['payment_plan'] == decision.payment_plan
        assert demo['amount_safe_to_pay'] == str(decision.amount_safe_to_pay)
        assert demo['badge'] == expected_badge_info['label']
        assert demo['badge_class'] == expected_badge_info['class']

        if demo['expected_label'] and demo['expected_label'] != expected_badge_info['label']:
            assert demo['warning'] is not None
            assert 'Development Warning' in demo['warning']
            assert demo['expected_label'] in demo['warning']
        else:
            assert demo['warning'] is None

def test_api_analyze_matches_engine_authoritative(client):
    for demo_cfg in DEMO_CONFIGS:
        req_id = demo_cfg['id']
        res = client.get(f'/api/analyze/{req_id}')
        assert res.status_code == 200
        payload = res.get_json()

        assert 'decision' in payload
        assert 'request' in payload
        assert 'profile' in payload
        assert 'chart' in payload
        assert 'evidence' in payload

        dec_resp = payload['decision']
        req = DATA['requests'][req_id]
        prof = DATA['profiles'][req.user_id]
        events = DATA['user_events'].get(req.user_id, [])
        amends = DATA['user_amendments'].get(req.user_id, [])
        opts = DATA['payment_opts'].get(req_id, [])
        fx_table = DATA['fx_table']

        decision, _ = make_decision(
            request=req,
            profile=prof,
            events=events,
            payment_options=opts,
            fx_table=fx_table,
            amendments=amends
        )

        expected_badge_info = STATUS_BADGE_MAP[decision.affordability_status]

        assert dec_resp['status'] == decision.affordability_status
        assert dec_resp['badge_label'] == expected_badge_info['label']
        assert dec_resp['badge_class'] == expected_badge_info['class']
        assert dec_resp['recommended_method'] == decision.recommended_payment_method
        assert dec_resp['amount_safe_to_pay'] == str(decision.amount_safe_to_pay)
        assert dec_resp['payment_plan'] == decision.payment_plan
        assert dec_resp['spending_changes_needed'] == decision.spending_changes_needed

        if demo_cfg.get('expected_label') and demo_cfg['expected_label'] != expected_badge_info['label']:
            assert payload['warning'] is not None
            assert dec_resp['warning'] is not None
            assert 'Development Warning' in payload['warning']
        else:
            assert payload['warning'] is None
            assert dec_resp['warning'] is None

def test_engine_never_overridden_by_expected_label(client):
    res = client.get('/api/analyze/request_01')
    assert res.status_code == 200
    data = res.get_json()
    assert data['decision']['status'] == 'not_affordable'
    assert data['decision']['badge_label'] == 'NOT RECOMMENDED'
    assert data['warning'] is not None
    assert 'SAFE NOW' in data['warning']
    assert 'not_affordable' in data['warning']
