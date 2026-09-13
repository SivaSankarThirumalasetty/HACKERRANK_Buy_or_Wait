import re
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
from src.models.domain import MessageEvidence, FinancialEvent, FinancialProfile

class MessageEffect(Enum):
    SALARY_INCREASE = 'salary_increase'
    SALARY_DECREASE_TEMP = 'salary_decrease_temp'  
    SALARY_RESUMED = 'salary_resumed'
    EMPLOYMENT_ENDED = 'employment_ended'
    ONE_EMPLOYER_ENDED = 'one_employer_ended'
    FIRST_SALARY = 'first_salary'
    SALARY_DATE_SHIFTED = 'salary_date_shifted'
    BASE_SALARY_ONLY = 'base_salary_only'
    BONUS_PENDING = 'bonus_pending'
    ARREARS_ADJUSTMENT = 'arrears_adjustment'
    INVOICE_CONFIRMED = 'invoice_confirmed'
    GIG_PAYOUT_PENDING = 'gig_payout_pending'
    REFUND_PENDING = 'refund_pending'
    INVESTMENT_VALUATION = 'investment_valuation'
    INVESTMENT_SALE_SETTLED = 'investment_sale_settled'
    PRIZE_CONFIRMED = 'prize_confirmed'
    PRIZE_PENDING = 'prize_pending'
    SCAM = 'scam'
    INTER_ACCOUNT_TRANSFER = 'inter_account_transfer'
    CARD_DISPUTE_NO_REVERSAL = 'card_dispute_no_reversal'
    FAILED_DEBIT_RETRY = 'failed_debit_retry'
    RENT_INCREASE_12PCT = 'rent_increase_12pct'
    WORK_EXPENSE_REIMBURSEMENT = 'work_expense_reimbursement'
    FX_RATE_NOTE = 'fx_rate_note'
    UNKNOWN = 'unknown'

def classify_message(msg: MessageEvidence) -> MessageEffect:
    text = msg.message_text.lower()
    if re.search(r'pay the release charge|bayar biaya pencairan', text):
        return MessageEffect.SCAM
    if re.search(r'salary has increased|naik menjadi|gaji bulanan anda naik', text):
        return MessageEffect.SALARY_INCREASE
    if re.search(r'temporary monthly pay|gaji bulanan sementara|reduced to|dikurangi menjadi|gaji.*sementara', text):
        return MessageEffect.SALARY_DECREASE_TEMP
    if re.search(r'contract has ended|kontrak musiman saat ini telah berakhir', text):
        return MessageEffect.EMPLOYMENT_ENDED
    if re.search(r'employment has ended|hubungan kerja anda telah berakhir', text):
        return MessageEffect.EMPLOYMENT_ENDED
    if re.search(r'one household employment record has ended|salah satu sumber pendapatan kerja rumah tangga telah berakhir', text):
        return MessageEffect.ONE_EMPLOYER_ENDED
    if re.search(r'resumes on|gaji rutin.*resumes|gaji rutin.*dimulai kembali', text):
        return MessageEffect.SALARY_RESUMED
    if re.search(r'first salary|gaji pertama', text):
        return MessageEffect.FIRST_SALARY
    if re.search(r'expected on|diperkirakan masuk pada', text):
        return MessageEffect.SALARY_DATE_SHIFTED
    if re.search(r'base salary|gaji pokok', text) and re.search(r'commission|komisi', text):
        return MessageEffect.BASE_SALARY_ONLY
    if re.search(r'quarterly bonus|bonus kuartalan', text):
        return MessageEffect.BONUS_PENDING
    if re.search(r'arrears adjustment|penyesuaian tunggakan', text):
        return MessageEffect.ARREARS_ADJUSTMENT
    if re.search(r'invoice payment|pembayaran faktur', text):
        return MessageEffect.INVOICE_CONFIRMED
    if re.search(r'payout is still pending|masih tertunda|payout.*pending', text):
        return MessageEffect.GIG_PAYOUT_PENDING
    if re.search(r'refund has been initiated|pengembalian dana sudah diproses|refund is still processing|pengembalian dana.*sedang diproses', text):
        return MessageEffect.REFUND_PENDING
    if re.search(r'market value|displayed value|nilai investasi|nilai yang ditampilkan', text):
        return MessageEffect.INVESTMENT_VALUATION
    if re.search(r'proceeds from your investment sale|hasil penjualan investasi', text):
        return MessageEffect.INVESTMENT_SALE_SETTLED
    if re.search(r'prize proceeds have reached|hadiah uang tunai telah masuk', text):
        return MessageEffect.PRIZE_CONFIRMED
    if re.search(r'prize claim has been verified|klaim hadiah anda sudah diverifikasi', text):
        return MessageEffect.PRIZE_PENDING
    if (re.search(r'matching debit and credit', text) or re.search(r'debit dan kredit dengan jumlah yang sama', text)) and (re.search(r'same account|transfer between your two accounts|transfer antara dua rekening', text)):
        return MessageEffect.INTER_ACCOUNT_TRANSFER
    if re.search(r'charge is still being investigated|tagihan kartu tambahan masih dalam penyelidikan|sengketa masih terbuka', text):
        return MessageEffect.CARD_DISPUTE_NO_REVERSAL
    if re.search(r'previous debit attempt failed|upaya debit sebelumnya gagal', text):
        return MessageEffect.FAILED_DEBIT_RETRY
    if re.search(r'renewed lease increases|menaikkan biaya sewa|sewa.*naik', text):
        return MessageEffect.RENT_INCREASE_12PCT
    if re.search(r'reimbursement for your earlier work expense|penggantian atas biaya kerja', text):
        return MessageEffect.WORK_EXPENSE_REIMBURSEMENT
    if re.search(r'salary of .* is confirmed for|gaji sebesar .* dikonfirmasi untuk|salary credit for', text):
        return MessageEffect.FIRST_SALARY
    if re.search(r'receipt has the final|receipt contains the final', text):
        return MessageEffect.UNKNOWN
    if re.search(r'foreign currency|mata uang asing', text) or re.search(r'foreign-currency refund', text):
        return MessageEffect.FX_RATE_NOTE
    if re.search(r'minimum payments due on two separate card accounts|separate card accounts', text):
        return MessageEffect.INTER_ACCOUNT_TRANSFER
    return MessageEffect.UNKNOWN

def extract_amount_from_message(text: str) -> Optional[Decimal]:
    match = re.search(r'(IDR|EUR|INR|ZAR|USD|Rp\.?)\s*([\d\.,]+)', text)
    if match:
        raw_val = match.group(2).rstrip('.,')
        # Check decimal pattern:
        # e.g. 1037.52 or 653.40 (dot followed by 2 digits at end)
        if re.search(r'\.\d{2}$', raw_val):
            # dot is decimal separator, remove commas if thousands
            clean_str = raw_val.replace(',', '')
        elif re.search(r',\d{2}$', raw_val):
            # comma is decimal separator (European), remove dots
            clean_str = raw_val.replace('.', '').replace(',', '.')
        else:
            # integer amount with possible dots or commas as thousand separators (e.g. 42.750.000 or 42,750,000)
            clean_str = raw_val.replace('.', '').replace(',', '')
        try:
            return Decimal(clean_str)
        except Exception:
            return None
    return None

def extract_date_from_message(text: str) -> Optional[date]:
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if match:
        return datetime.strptime(match.group(1), '%Y-%m-%d').date()
    match2 = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text)
    if match2:
        try:
            return datetime.strptime(match2.group(1), '%d %B %Y').date()
        except:
            pass
    return None

@dataclass
class MessageAmendment:
    effect: MessageEffect
    new_amount: Optional[Decimal]
    new_currency: Optional[str]
    effective_date: Optional[date]
    is_one_time: bool
    source_user_id: str
    source_message_id: str

def parse_message(msg: MessageEvidence) -> MessageAmendment:
    effect = classify_message(msg)
    amount = extract_amount_from_message(msg.message_text)
    dt = extract_date_from_message(msg.message_text)
    currency = None
    if amount is not None:
        match = re.search(r'(IDR|EUR|INR|ZAR|USD)', msg.message_text)
        if match:
            currency = match.group(1)
        elif 'Rp' in msg.message_text:
            currency = 'IDR'
    return MessageAmendment(
        effect=effect,
        new_amount=amount,
        new_currency=currency,
        effective_date=dt,
        is_one_time=(effect in [MessageEffect.ARREARS_ADJUSTMENT]),
        source_user_id=msg.user_id,
        source_message_id=msg.message_id
    )

def apply_amendments_to_events(events: List[FinancialEvent], amendments: List[MessageAmendment], profile: FinancialProfile, as_of_date: date, forecast_end: date) -> List[FinancialEvent]:
    import copy
    new_events = [copy.copy(ev) for ev in events]
    for am in amendments:
        if am.source_user_id != profile.user_id:
            continue
        
        if am.effect == MessageEffect.SALARY_INCREASE:
            if am.new_amount is not None:
                for ev in new_events:
                    if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= (am.effective_date or as_of_date):
                        ev.amount = am.new_amount
                        
        elif am.effect == MessageEffect.SALARY_DECREASE_TEMP:
            if am.new_amount is not None:
                # Modifies ONLY the next upcoming salary
                upcoming_salaries = [ev for ev in new_events if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= as_of_date]
                upcoming_salaries.sort(key=lambda x: x.settlement_date)
                if upcoming_salaries:
                    upcoming_salaries[0].amount = am.new_amount
                    
        elif am.effect == MessageEffect.EMPLOYMENT_ENDED:
            for ev in new_events:
                if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= (am.effective_date or as_of_date):
                    ev.status = 'cancelled'
                    
        elif am.effect == MessageEffect.ONE_EMPLOYER_ENDED:
            if am.new_amount is not None:
                for ev in new_events:
                    if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= (am.effective_date or as_of_date):
                        ev.amount = am.new_amount
                        
        elif am.effect == MessageEffect.RENT_INCREASE_12PCT:
            for ev in new_events:
                if 'rent' in ev.category.lower() and ev.direction == 'debit' and ev.settlement_date >= (am.effective_date or as_of_date):
                    if ev.amount:
                        ev.amount = ev.amount * Decimal('1.12')
                        
        elif am.effect == MessageEffect.BASE_SALARY_ONLY:
            for ev in new_events:
                if ev.category == 'commission' and ev.direction == 'credit':
                    ev.status = 'cancelled'
                elif ev.category == 'salary' and ev.direction == 'credit' and am.new_amount is not None:
                    if ev.settlement_date >= (am.effective_date or as_of_date):
                        ev.amount = am.new_amount
                        
        elif am.effect == MessageEffect.SALARY_DATE_SHIFTED:
            if am.effective_date is not None:
                upcoming_salaries = [ev for ev in new_events if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= as_of_date]
                upcoming_salaries.sort(key=lambda x: x.settlement_date)
                if upcoming_salaries:
                    upcoming_salaries[0].settlement_date = am.effective_date
                    upcoming_salaries[0].event_date = am.effective_date
                    
        elif am.effect == MessageEffect.ARREARS_ADJUSTMENT:
            # One-off extra credit on the next payroll date
            if am.new_amount is not None:
                upcoming_salaries = [ev for ev in new_events if ev.category == 'salary' and ev.direction == 'credit' and ev.settlement_date >= as_of_date]
                upcoming_salaries.sort(key=lambda x: x.settlement_date)
                target_date = upcoming_salaries[0].settlement_date if upcoming_salaries else as_of_date
                new_events.append(FinancialEvent(
                    event_id=f"arrears_{am.source_message_id}",
                    user_id=profile.user_id,
                    event_date=target_date,
                    settlement_date=target_date,
                    event_type='income',
                    description='one-time arrears adjustment',
                    amount=am.new_amount,
                    currency=am.new_currency or profile.home_currency,
                    direction='credit',
                    status='scheduled',
                    flexibility='fixed',
                    category='salary',
                    linked_event_id=None
                ))
                
        elif am.effect in [MessageEffect.INVOICE_CONFIRMED, MessageEffect.FIRST_SALARY]:
            if am.new_amount is not None and am.effective_date is not None:
                new_events.append(FinancialEvent(
                    event_id=f"msg_credit_{am.source_message_id}",
                    user_id=profile.user_id,
                    event_date=am.effective_date,
                    settlement_date=am.effective_date,
                    event_type='income',
                    description='confirmed income from message',
                    amount=am.new_amount,
                    currency=am.new_currency or profile.home_currency,
                    direction='credit',
                    status='scheduled',
                    flexibility='fixed',
                    category='salary' if am.effect == MessageEffect.FIRST_SALARY else 'other',
                    linked_event_id=None
                ))

    return new_events
