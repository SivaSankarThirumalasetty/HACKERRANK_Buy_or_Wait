import os
import sys
import json
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Flask, render_template, request, jsonify, send_from_directory

# Configure project path
base_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(base_dir)
repo_root = os.path.dirname(src_dir)
sys.path.insert(0, repo_root)

from src.data.loaders import load_all, load_requests
from src.normalization.events import normalize_events
from src.currency.converter import ExchangeRateTable
from src.evidence.messages import parse_message
from src.affordability.engine import make_decision
from src.forecasting.cashflow import build_cashflow_forecast
from src.evidence.image_parser import IMAGE_RATIONALE_MAP
from src.evidence.images import IMAGE_AMOUNTS

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'), static_folder=os.path.join(base_dir, 'static'))

# In-memory storage for dataset
DATA = {}

def init_data():
    dataset_dir = os.path.join(repo_root, 'dataset')
    eval_requests = load_requests(dataset_dir, 'requests.csv')
    sample_requests = load_requests(dataset_dir, 'sample_requests.csv')
    
    profiles, events, _, payment_opts, messages, rates = load_all(dataset_dir)
    norm_events = normalize_events(events)
    fx_table = ExchangeRateTable(rates)

    # Images metadata
    images_meta = {}
    images_csv = os.path.join(dataset_dir, 'images.csv')
    if os.path.exists(images_csv):
        with open(images_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                images_meta[row['request_id']] = {
                    'image_id': row['image_id'],
                    'user_id': row['user_id'],
                    'related_event_id': row['related_event_id'],
                    'filename': f"{row['image_id']}.png"
                }

    user_events = {}
    for ev in norm_events:
        user_events.setdefault(ev.user_id, []).append(ev)

    user_messages = {}
    for m in messages:
        user_messages.setdefault(m.user_id, []).append(m)

    user_amendments = {}
    for m in messages:
        am = parse_message(m)
        user_amendments.setdefault(m.user_id, []).append(am)

    all_reqs = {r.request_id: r for r in sample_requests + eval_requests}

    DATA['profiles'] = profiles
    DATA['requests'] = all_reqs
    DATA['eval_requests'] = eval_requests
    DATA['sample_requests'] = sample_requests
    DATA['payment_opts'] = payment_opts
    DATA['user_events'] = user_events
    DATA['user_messages'] = user_messages
    DATA['user_amendments'] = user_amendments
    DATA['images_meta'] = images_meta
    DATA['fx_table'] = fx_table

init_data()

STATUS_BADGE_MAP = {
    'affordable_now': {'label': 'SAFE NOW', 'class': 'badge-safe-now'},
    'affordable_with_plan': {'label': 'SAFE WITH PLAN', 'class': 'badge-plan'},
    'affordable_later': {'label': 'WAIT', 'class': 'badge-wait'},
    'not_affordable': {'label': 'NOT RECOMMENDED', 'class': 'badge-not-recommended'}
}

DEMO_CONFIGS = [
    {'id': 'request_01', 'description': 'ZAR 25,256 Laptop Purchase', 'expected_label': 'SAFE NOW'},
    {'id': 'request_02', 'description': 'IDR 46,018,000 Travel', 'expected_label': 'SAFE WITH PLAN'},
    {'id': 'request_03', 'description': 'IDR 5,491,000 Education', 'expected_label': 'WAIT'},
    {'id': 'request_05', 'description': 'ZAR 15,488 Debt Repayment', 'expected_label': 'NOT RECOMMENDED'},
    {'id': 'request_138', 'description': 'EUR 1,256.94 Healthcare', 'expected_label': 'SAFE WITH PLAN'},
    {'id': 'request_35', 'description': 'INR 3,650 Vehicle Repair', 'expected_label': 'SAFE NOW'},
    {'id': 'request_39', 'description': 'INR 208,600 Housing', 'expected_label': 'NOT RECOMMENDED'}
]

def evaluate_request_dynamically(request_id: str):
    """
    Evaluates a request dynamically using the authoritative decision engine.
    Returns (decision, trace, error_str).
    """
    if request_id not in DATA['requests']:
        return None, None, f"Request {request_id} not found"

    req = DATA['requests'][request_id]
    user_id = req.user_id
    prof = DATA['profiles'].get(user_id)
    if not prof:
        return None, None, f"Profile for user {user_id} not found"

    u_events = DATA['user_events'].get(user_id, [])
    u_amends = DATA['user_amendments'].get(user_id, [])
    opts = DATA['payment_opts'].get(request_id, [])
    fx_table = DATA['fx_table']

    decision, trace = make_decision(
        request=req,
        profile=prof,
        events=u_events,
        payment_options=opts,
        fx_table=fx_table,
        amendments=u_amends
    )
    return decision, trace, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/requests')
def get_requests():
    # Dynamically evaluate all demo requests via the authoritative decision engine
    demos = []
    for d_cfg in DEMO_CONFIGS:
        req_id = d_cfg['id']
        if req_id not in DATA['requests']:
            continue
        req = DATA['requests'][req_id]
        decision, trace, err = evaluate_request_dynamically(req_id)
        if err or not decision:
            continue

        badge_info = STATUS_BADGE_MAP.get(
            decision.affordability_status,
            {'label': decision.affordability_status.upper(), 'class': 'badge-wait'}
        )
        computed_badge = badge_info['label']
        expected_label = d_cfg.get('expected_label')

        warning = None
        if expected_label and computed_badge != expected_label:
            warning = (
                f"Development Warning: Engine computed '{decision.affordability_status}' ({computed_badge}), "
                f"which differs from legacy expected label '{expected_label}'. "
                f"The dynamic decision engine output is preserved as the authoritative source of truth."
            )
            app.logger.warning(f"[{req_id}] {warning}")

        demos.append({
            'id': req_id,
            'title': f"{req_id}: {d_cfg['description']} ({computed_badge})",
            'badge': computed_badge,
            'badge_class': badge_info['class'],
            'affordability_status': decision.affordability_status,
            'recommended_payment_method': decision.recommended_payment_method,
            'payment_plan': decision.payment_plan,
            'amount_safe_to_pay': str(decision.amount_safe_to_pay),
            'earliest_date_for_full_payment': decision.earliest_date_for_full_payment.strftime('%Y-%m-%d') if decision.earliest_date_for_full_payment else 'None',
            'expected_label': expected_label,
            'warning': warning
        })

    all_items = []
    # Add samples first
    for r in DATA['sample_requests']:
        all_items.append({
            'id': r.request_id,
            'user_id': r.user_id,
            'amount': str(r.requested_amount),
            'currency': r.currency,
            'type': r.request_type,
            'date': r.request_date.strftime('%Y-%m-%d'),
            'label': f"[{r.request_id}] {r.user_id} - {r.currency} {r.requested_amount} ({r.request_type}) [Sample]"
        })
    # Add evaluation requests
    for r in DATA['eval_requests']:
        all_items.append({
            'id': r.request_id,
            'user_id': r.user_id,
            'amount': str(r.requested_amount),
            'currency': r.currency,
            'type': r.request_type,
            'date': r.request_date.strftime('%Y-%m-%d'),
            'label': f"[{r.request_id}] {r.user_id} - {r.currency} {r.requested_amount} ({r.request_type})"
        })

    return jsonify({
        'demos': demos,
        'all_requests': all_items
    })

@app.route('/api/analyze/<request_id>')
def analyze_request(request_id):
    if request_id not in DATA['requests']:
        return jsonify({'error': f'Request {request_id} not found'}), 404

    req = DATA['requests'][request_id]
    user_id = req.user_id
    prof = DATA['profiles'].get(user_id)
    if not prof:
        return jsonify({'error': f'Profile for user {user_id} not found'}), 404

    u_events = DATA['user_events'].get(user_id, [])
    u_amends = DATA['user_amendments'].get(user_id, [])
    u_msgs = DATA['user_messages'].get(user_id, [])
    opts = DATA['payment_opts'].get(request_id, [])
    fx_table = DATA['fx_table']

    # Execute decision engine
    decision, trace = make_decision(
        request=req,
        profile=prof,
        events=u_events,
        payment_options=opts,
        fx_table=fx_table,
        amendments=u_amends
    )

    # 90-day base forecast points for chart
    forecast = build_cashflow_forecast(
        profile=prof,
        events=u_events,
        request_date=req.request_date,
        fx_table=fx_table,
        amendments=u_amends
    )

    chart_data = {
        'dates': [f.day.strftime('%Y-%m-%d') for f in forecast],
        'balances': [float(f.closing_balance) for f in forecast],
        'threshold': float(prof.minimum_balance_to_keep)
    }

    # Format relevant evidence
    messages_payload = []
    for m in u_msgs:
        messages_payload.append({
            'id': m.message_id,
            'sent_at': m.sent_at.strftime('%Y-%m-%d %H:%M') if m.sent_at else 'Unknown',
            'source': m.source_type,
            'text': m.message_text
        })

    image_payload = None
    if request_id in DATA['images_meta']:
        im = DATA['images_meta'][request_id]
        ev_id = im['related_event_id']
        ocr_info = IMAGE_AMOUNTS.get(ev_id)
        rationale = IMAGE_RATIONALE_MAP.get(ev_id, 'OCR verified receipt')
        image_payload = {
            'image_id': im['image_id'],
            'url': f"/static/images/{im['filename']}",
            'event_id': ev_id,
            'extracted_amount': str(ocr_info[1]) if ocr_info else None,
            'extracted_currency': ocr_info[0] if ocr_info else None,
            'rationale': rationale
        }

    # Upcoming confirmed income & protected expenses
    forecast_end = req.request_date + timedelta(days=90)
    upcoming_income = sum(
        ev.amount for ev in u_events
        if ev.direction == 'credit' and ev.status in ['settled', 'scheduled'] and ev.amount and req.request_date <= ev.settlement_date <= forecast_end
    )
    protected_expenses = sum(
        ev.amount for ev in u_events
        if ev.direction == 'debit' and ev.category in prof.expense_categories_to_protect and ev.amount and req.request_date <= ev.settlement_date <= forecast_end
    )

    # Status badge mapping using global STATUS_BADGE_MAP
    badge_info = STATUS_BADGE_MAP.get(
        decision.affordability_status,
        {'label': decision.affordability_status.upper(), 'class': 'badge-wait'}
    )

    # Check if request has a legacy expected demo label and verify alignment
    expected_cfg = next((d for d in DEMO_CONFIGS if d['id'] == request_id), None)
    warning = None
    if expected_cfg and expected_cfg.get('expected_label'):
        exp_label = expected_cfg['expected_label']
        if badge_info['label'] != exp_label:
            warning = (
                f"Development Warning: Engine computed '{decision.affordability_status}' ({badge_info['label']}), "
                f"which differs from legacy expected label '{exp_label}'. "
                f"The dynamic decision engine output is preserved as the authoritative source of truth."
            )
            app.logger.warning(f"[{request_id}] {warning}")

    return jsonify({
        'warning': warning,
        'request': {
            'id': req.request_id,
            'user_id': req.user_id,
            'type': req.request_type,
            'amount': str(req.requested_amount),
            'currency': prof.home_currency,
            'request_date': req.request_date.strftime('%Y-%m-%d'),
            'desired_completion_date': req.desired_completion_date.strftime('%Y-%m-%d') if req.desired_completion_date else 'N/A',
            'allows_partial_payment': req.allows_partial_payment,
            'request_text': req.request_text
        },
        'profile': {
            'user_id': prof.user_id,
            'home_currency': prof.home_currency,
            'current_balance': str(prof.current_available_balance),
            'minimum_balance': str(prof.minimum_balance_to_keep),
            'priorities': prof.financial_priorities,
            'protected_categories': prof.expense_categories_to_protect,
            'reduce_categories': prof.expense_categories_to_reduce,
            'stop_categories': prof.expense_categories_to_stop,
            'payment_preferences': prof.payment_methods,
            'max_installment_months': prof.max_installment_months,
            'upcoming_income': str(upcoming_income),
            'protected_expenses': str(protected_expenses)
        },
        'decision': {
            'status': decision.affordability_status,
            'badge_label': badge_info['label'],
            'badge_class': badge_info['class'],
            'recommended_method': decision.recommended_payment_method,
            'amount_safe_to_pay': str(decision.amount_safe_to_pay),
            'payment_plan': decision.payment_plan,
            'earliest_date_for_full_payment': decision.earliest_date_for_full_payment.strftime('%Y-%m-%d') if decision.earliest_date_for_full_payment else 'None',
            'spending_changes_needed': decision.spending_changes_needed,
            'explanation': decision.decision_explanation,
            'warning': warning
        },
        'available_options': [
            {
                'id': opt.payment_option_id,
                'method': opt.payment_method,
                'payments': opt.number_of_payments,
                'amount': str(opt.payment_amount),
                'fee': str(opt.financing_fee),
                'total': str(opt.total_payable_amount),
                'frequency': f"{opt.payment_frequency_days} days" if opt.payment_frequency_days else "N/A",
                'start_date': opt.first_payment_date.strftime('%Y-%m-%d')
            }
            for opt in opts
        ],
        'evidence': {
            'messages': messages_payload,
            'image': image_payload
        },
        'chart': chart_data,
        'trace': trace.to_dict() if trace else None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Financial Agent Dashboard on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
