import csv
import os
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from src.models.domain import FinancialProfile, FinancialEvent, Request, PaymentOption, MessageEvidence

def parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def parse_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def parse_decimal(val_str: str) -> Optional[Decimal]:
    if not val_str or not val_str.strip():
        return None
    return Decimal(val_str.strip())

def parse_list(val_str: str) -> List[str]:
    if not val_str or not val_str.strip():
        return []
    return [v.strip() for v in val_str.split('|') if v.strip()]

def load_profiles(dataset_dir: str) -> Dict[str, FinancialProfile]:
    profiles = {}
    path = os.path.join(dataset_dir, 'financial_profiles.csv')
    if not os.path.exists(path):
        return profiles
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('user_id', '').strip():
                continue
            max_inst = row.get('max_installment_months', '').strip()
            profiles[row['user_id']] = FinancialProfile(
                user_id=row['user_id'],
                home_currency=row['home_currency'],
                current_available_balance=parse_decimal(row['current_available_balance']),
                minimum_balance_to_keep=parse_decimal(row['minimum_balance_to_keep']),
                financial_priorities=parse_list(row['financial_priorities']),
                expense_categories_to_protect=parse_list(row['expense_categories_to_protect']),
                expense_categories_to_reduce=parse_list(row['expense_categories_user_is_willing_to_reduce']),
                expense_categories_to_stop=parse_list(row['expense_categories_user_is_willing_to_stop']),
                payment_methods=parse_list(row['payment_methods_user_will_consider']),
                max_installment_months=int(max_inst) if max_inst else None
            )
    return profiles

def load_events(dataset_dir: str) -> List[FinancialEvent]:
    events = []
    path = os.path.join(dataset_dir, 'financial_events.csv')
    if not os.path.exists(path):
        return events
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('event_id', '').strip():
                continue
            events.append(FinancialEvent(
                event_id=row['event_id'],
                user_id=row['user_id'],
                event_date=parse_date(row['event_date']),
                settlement_date=parse_date(row['settlement_date']),
                event_type=row['event_type'],
                description=row.get('description', ''),
                amount=parse_decimal(row['amount']),
                currency=row['currency'],
                direction=row['direction'],
                status=row['status'],
                flexibility=row['flexibility'],
                category=row['category'],
                linked_event_id=row.get('linked_event_id', '').strip() or None,
                minimum_allowed_amount=parse_decimal(row.get('minimum_allowed_amount', ''))
            ))
    return events

def load_requests(dataset_dir: str, filename: str = 'requests.csv') -> List[Request]:
    requests = []
    path = os.path.join(dataset_dir, filename)
    if not os.path.exists(path):
        return requests
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('request_id', '').strip():
                continue
            requests.append(Request(
                request_id=row['request_id'],
                user_id=row['user_id'],
                request_date=parse_date(row['request_date']),
                request_type=row['request_type'],
                requested_amount=parse_decimal(row['requested_amount']),
                currency=row.get('currency', ''),
                desired_completion_date=parse_date(row['desired_completion_date']),
                allows_partial_payment=row['allows_partial_payment'].lower() == 'true',
                request_text=row.get('request_text', '')
            ))
    return requests

def load_payment_options(dataset_dir: str) -> Dict[str, List[PaymentOption]]:
    options = {}
    path = os.path.join(dataset_dir, 'request_payment_options.csv')
    if not os.path.exists(path):
        return options
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('payment_option_id', '').strip():
                continue
            req_id = row['request_id']
            freq = row.get('payment_frequency_days', '').strip()
            opt = PaymentOption(
                payment_option_id=row['payment_option_id'],
                request_id=req_id,
                payment_method=row['payment_method'],
                number_of_payments=int(row['number_of_payments']),
                payment_amount=parse_decimal(row['payment_amount']),
                payment_frequency_days=int(freq) if freq else None,
                financing_fee=parse_decimal(row['financing_fee']),
                total_payable_amount=parse_decimal(row['total_payable_amount']),
                first_payment_date=parse_date(row['first_payment_date'])
            )
            if req_id not in options:
                options[req_id] = []
            options[req_id].append(opt)
    return options

def load_messages(dataset_dir: str) -> List[MessageEvidence]:
    messages = []
    path = os.path.join(dataset_dir, 'messages.csv')
    if not os.path.exists(path):
        return messages
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('message_id', '').strip():
                continue
            messages.append(MessageEvidence(
                message_id=row['message_id'],
                user_id=row['user_id'],
                request_id=row.get('request_id', '').strip() or None,
                related_event_id=row.get('related_event_id', '').strip() or None,
                sent_at=parse_datetime(row['sent_at']),
                source_type=row['source_type'],
                message_text=row['message_text']
            ))
    return messages

def load_exchange_rates(dataset_dir: str) -> List[Dict]:
    rates = []
    path = os.path.join(dataset_dir, 'exchange_rates.csv')
    if not os.path.exists(path):
        return rates
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('rate_date', '').strip():
                continue
            rates.append({
                'date': parse_date(row['rate_date']),
                'from_currency': row['from_currency'],
                'to_currency': row['to_currency'],
                'rate': parse_decimal(row['rate'])
            })
    return rates

def load_all(dataset_dir: str) -> Tuple[Dict[str, FinancialProfile], List[FinancialEvent], List[Request], Dict[str, List[PaymentOption]], List[MessageEvidence], List[Dict]]:
    return (
        load_profiles(dataset_dir),
        load_events(dataset_dir),
        load_requests(dataset_dir),
        load_payment_options(dataset_dir),
        load_messages(dataset_dir),
        load_exchange_rates(dataset_dir)
    )
