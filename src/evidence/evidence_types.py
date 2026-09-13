from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from src.evidence.confidence import ConfidenceLevel

@dataclass
class StructuredEvidence:
    event_id: Optional[str]
    evidence_type: str
    extracted_value: Any
    source: str
    confidence: ConfidenceLevel
    source_timestamp: Optional[datetime]
    rationale: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
