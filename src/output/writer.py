import csv
from typing import List, Dict
from decimal import Decimal
from src.models.domain import Decision

def format_decimal_output(val) -> str:
    if val is None:
        return ''
    if isinstance(val, (int, Decimal, float)):
        d = Decimal(str(val))
        s = f"{d:f}"
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s
    return str(val)

def decision_to_row(decision: Decision) -> Dict:
    return {
        'request_id': decision.request_id,
        'amount_safe_to_pay': format_decimal_output(decision.amount_safe_to_pay),
        'affordability_status': decision.affordability_status,
        'recommended_payment_method': decision.recommended_payment_method,
        'payment_plan': decision.payment_plan,
        'earliest_date_for_full_payment': decision.earliest_date_for_full_payment.strftime('%Y-%m-%d') if decision.earliest_date_for_full_payment else '',
        'spending_changes_needed': decision.spending_changes_needed,
        'decision_explanation': decision.decision_explanation
    }

def write_output_csv(decisions: List[Decision], output_path: str) -> None:
    fieldnames = [
        'request_id', 'amount_safe_to_pay', 'affordability_status',
        'recommended_payment_method', 'payment_plan', 'earliest_date_for_full_payment',
        'spending_changes_needed', 'decision_explanation'
    ]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in decisions:
            writer.writerow(decision_to_row(d))
