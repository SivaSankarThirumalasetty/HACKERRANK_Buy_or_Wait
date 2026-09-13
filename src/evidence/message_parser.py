import re
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from src.models.domain import MessageEvidence
from src.evidence.confidence import ConfidenceLevel
from src.evidence.evidence_types import StructuredEvidence
from src.evidence.messages import classify_message, extract_amount_from_message, extract_date_from_message, MessageEffect

# Injection attack / override pattern check
INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?(previous|prior)\s+(rules|instructions)',
    r'mark\s+(this\s+)?(purchase\s+)?affordable',
    r'override\s+(the\s+)?(rules|specification|system)',
    r'system\s+prompt',
    r'disregard\s+(the\s+)?(limits|balances|minimum)',
    r'you\s+must\s+approve',
    r'grant\s+full\s+affordability',
]

def detect_security_injection(text: str) -> bool:
    lower_text = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower_text):
            return True
    return False

def parse_message_evidence(msg: MessageEvidence) -> StructuredEvidence:
    """
    Parses untrusted message content into a StructuredEvidence object.
    Enforces strict security checks to reject injection attempts and instructions
    purporting to override challenge constraints.
    """
    text = msg.message_text

    # Security check: detect prompt injections or hostile instruction text
    if detect_security_injection(text):
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="security_injection_ignored",
            extracted_value=None,
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.UNRELIABLE,
            source_timestamp=msg.sent_at,
            rationale="Hostile instruction or prompt injection attempt detected and rejected; untrusted content ignored.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    effect = classify_message(msg)
    extracted_amount = extract_amount_from_message(text)
    extracted_date = extract_date_from_message(text)

    # Determine structured evidence type and rationale
    if effect == MessageEffect.SCAM:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="scam_attempt",
            extracted_value=None,
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.UNRELIABLE,
            source_timestamp=msg.sent_at,
            rationale="Advance-fee scam detected; financial effect zeroed.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.SALARY_INCREASE:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="salary_information",
            extracted_value={"new_amount": extracted_amount, "effective_date": extracted_date, "action": "increase"},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Employer confirmed recurring monthly salary increase to {extracted_amount} starting {extracted_date}.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.SALARY_DECREASE_TEMP:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="salary_information",
            extracted_value={"new_amount": extracted_amount, "action": "temporary_reduction"},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Employer confirmed temporary salary reduction to {extracted_amount} for next cycle.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.EMPLOYMENT_ENDED:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="cancellation",
            extracted_value={"target": "salary_stream", "action": "ended"},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale="Employer notification that contract or employment has ended.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.RENT_INCREASE_12PCT:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="recurring_expense_information",
            extracted_value={"rate_multiplier": Decimal('1.12'), "category": "rent"},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale="Service provider confirmed 12% increase on recurring monthly rent lease renewal.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.FAILED_DEBIT_RETRY:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="payment_commitment",
            extracted_value={"status": "retry_pending", "action": "reserve_debit"},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale="Bank indicated failed debit will be re-attempted; obligation remains active.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.CARD_DISPUTE_NO_REVERSAL:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="transaction_clarification",
            extracted_value={"status": "under_investigation", "reversal_posted": False},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale="Bank confirmed card charge dispute is under investigation with no reversal credited.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.INVOICE_CONFIRMED:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="confirmation",
            extracted_value={"amount": extracted_amount, "settlement_date": extracted_date},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Service provider confirmed invoice approval of {extracted_amount} settling on {extracted_date}.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.FIRST_SALARY:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="salary_information",
            extracted_value={"first_salary_amount": extracted_amount, "settlement_date": extracted_date},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Employer confirmed initial salary credit of {extracted_amount} on {extracted_date}.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.SALARY_DATE_SHIFTED:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="changed_date",
            extracted_value={"new_date": extracted_date},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Employer confirmed payroll date shift to {extracted_date}.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect == MessageEffect.ARREARS_ADJUSTMENT:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="amendment",
            extracted_value={"arrears_amount": extracted_amount, "is_one_time": True},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale=f"Employer confirmed one-time arrears adjustment of {extracted_amount}.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    if effect in [MessageEffect.REFUND_PENDING, MessageEffect.GIG_PAYOUT_PENDING, MessageEffect.BONUS_PENDING, MessageEffect.PRIZE_PENDING]:
        return StructuredEvidence(
            event_id=msg.related_event_id,
            evidence_type="delayed_payment",
            extracted_value={"pending": True, "confirmed": False},
            source=f"message:{msg.message_id}:{msg.source_type}",
            confidence=ConfidenceLevel.HIGH,
            source_timestamp=msg.sent_at,
            rationale="Notice confirms pending status; funds not yet settled or approved.",
            user_id=msg.user_id,
            request_id=msg.request_id
        )

    # General clarification / unknown
    return StructuredEvidence(
        event_id=msg.related_event_id,
        evidence_type="transaction_clarification",
        extracted_value={"text": text},
        source=f"message:{msg.message_id}:{msg.source_type}",
        confidence=ConfidenceLevel.MEDIUM,
        source_timestamp=msg.sent_at,
        rationale="Informational message without specific numeric or status amendment.",
        user_id=msg.user_id,
        request_id=msg.request_id
    )
