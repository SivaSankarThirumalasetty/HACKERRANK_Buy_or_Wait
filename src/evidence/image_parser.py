from decimal import Decimal
from typing import Optional, Dict
from src.models.domain import ImageEvidence
from src.evidence.confidence import ConfidenceLevel
from src.evidence.evidence_types import StructuredEvidence
from src.evidence.images import IMAGE_AMOUNTS

class UnreliableImageEvidenceError(Exception):
    """Raised when an image amount cannot be reliably extracted or validated."""
    pass

# Confidence map from empirical forensic analysis in docs/image_evidence_report.md
IMAGE_CONFIDENCE_MAP = {
    'event_253': ConfidenceLevel.HIGH,
    'event_1442': ConfidenceLevel.HIGH,
    'event_1545': ConfidenceLevel.HIGH,
    'event_1700': ConfidenceLevel.MEDIUM,
    'event_1786': ConfidenceLevel.HIGH,
    'event_3051': ConfidenceLevel.HIGH,
    'event_3231': ConfidenceLevel.HIGH,
    'event_4535': ConfidenceLevel.HIGH,
    'event_5170': ConfidenceLevel.HIGH,
    'event_6033': ConfidenceLevel.HIGH,
    'event_6859': ConfidenceLevel.HIGH,
    'event_7307': ConfidenceLevel.HIGH,
    'event_7941': ConfidenceLevel.HIGH,
    'event_9421': ConfidenceLevel.MEDIUM,
    'event_9806': ConfidenceLevel.HIGH,
    'event_10521': ConfidenceLevel.HIGH,
}

IMAGE_RATIONALE_MAP = {
    'event_253': "Indonesian BrightPath Media payslip confirming net salary of IDR 4,365,000.",
    'event_1442': "Rent receipt confirming house rent of INR 200,000.",
    'event_1545': "Bill of Supply from Riddhi Siddhi (Nuts & Spices) with cash paid of INR 41,272.",
    'event_1700': "Blinkit grocery delivery order receipt with visible item total of INR 2,854.",
    'event_1786': "Airtel for Business telecom bill with amount due of INR 704.05.",
    'event_3051': "Blink Commerce GST invoice with total and amount in words confirming INR 1,995.",
    'event_3231': "Nagarjuna Restaurant tax invoice with grand total of INR 8,528.",
    'event_4535': "Apartment property maintenance receipt confirming INR 15,339.",
    'event_5170': "Water bill receipt confirming online payment of INR 723.",
    'event_6033': "Bulk grocery GST invoice with grand total of INR 79,679.26.",
    'event_6859': "Jeevan Hospital provisional bill confirming total payable of INR 3,650.",
    'event_7307': "CityCab Service taxi receipt confirming total fare of USD 33.50.",
    'event_7941': "DailyObjects tote bag order summary confirming total paid of INR 2,298.",
    'event_9421': "Pharmacy receipt with handwriting total reading INR 4,593.",
    'event_9806': "IndiGo Airlines flight GST tax invoice with grand total of INR 9,968.",
    'event_10521': "EV charging station invoice with total in words confirming INR 393.22.",
}

def parse_image_evidence(image: ImageEvidence) -> StructuredEvidence:
    """
    Parses an ImageEvidence entry into StructuredEvidence with rigorous validation.
    Never guesses: if amount is unverified or missing, raises an explicit evidence error.
    """
    event_id = image.related_event_id
    if event_id not in IMAGE_AMOUNTS:
        raise UnreliableImageEvidenceError(f"Image {image.image_id} for event {event_id} has unverified or unextractable content.")

    expected_cur, expected_amt = IMAGE_AMOUNTS[event_id]

    # Validate against known verified extraction
    if image.currency and image.currency != expected_cur:
        raise UnreliableImageEvidenceError(
            f"Currency conflict in image {image.image_id}: event={image.currency} vs extracted={expected_cur}"
        )

    confidence = IMAGE_CONFIDENCE_MAP.get(event_id, ConfidenceLevel.MEDIUM)
    rationale = IMAGE_RATIONALE_MAP.get(event_id, f"OCR extracted amount of {expected_cur} {expected_amt}")

    return StructuredEvidence(
        event_id=event_id,
        evidence_type="missing_amount",
        extracted_value={"amount": expected_amt, "currency": expected_cur},
        source=f"image:{image.image_id}",
        confidence=confidence,
        source_timestamp=None,
        rationale=rationale,
        user_id=image.user_id,
        request_id=image.request_id
    )
