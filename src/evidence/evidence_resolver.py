from typing import List, Dict, Optional
from collections import defaultdict
from src.models.domain import MessageEvidence, ImageEvidence, FinancialEvent
from src.evidence.evidence_types import StructuredEvidence
from src.evidence.message_parser import parse_message_evidence
from src.evidence.image_parser import parse_image_evidence
from src.evidence.confidence import ConfidenceLevel

class EvidenceResolver:
    """
    Resolves, filters, and consolidates all structured evidence from untrusted sources
    (messages, images) for a user or request.
    Applies security filters to ensure untrusted content never overrides core financial rules.
    """

    def __init__(self, messages: List[MessageEvidence], images: List[ImageEvidence]):
        self.raw_messages = messages
        self.raw_images = images
        self._parsed_evidence: List[StructuredEvidence] = []
        self._by_event: Dict[str, List[StructuredEvidence]] = defaultdict(list)
        self._by_user: Dict[str, List[StructuredEvidence]] = defaultdict(list)
        self._by_request: Dict[str, List[StructuredEvidence]] = defaultdict(list)
        self._resolve_all()

    def _resolve_all(self):
        # 1. Parse all messages
        for msg in self.raw_messages:
            ev = parse_message_evidence(msg)
            # Exclude rejected prompt injections and scams from actionable evidence
            if ev.confidence != ConfidenceLevel.UNRELIABLE:
                self._parsed_evidence.append(ev)
                if ev.event_id:
                    self._by_event[ev.event_id].append(ev)
                if ev.user_id:
                    self._by_user[ev.user_id].append(ev)
                if ev.request_id:
                    self._by_request[ev.request_id].append(ev)

        # 2. Parse all images
        for img in self.raw_images:
            try:
                ev = parse_image_evidence(img)
                self._parsed_evidence.append(ev)
                if ev.event_id:
                    self._by_event[ev.event_id].append(ev)
                if ev.user_id:
                    self._by_user[ev.user_id].append(ev)
                if ev.request_id:
                    self._by_request[ev.request_id].append(ev)
            except Exception:
                # Discard or flag unreliable evidence
                continue

    def get_evidence_for_event(self, event_id: str) -> List[StructuredEvidence]:
        return self._by_event.get(event_id, [])

    def get_evidence_for_user(self, user_id: str) -> List[StructuredEvidence]:
        return self._by_user.get(user_id, [])

    def get_evidence_for_request(self, request_id: str) -> List[StructuredEvidence]:
        return self._by_request.get(request_id, [])

    def get_all_valid_evidence(self) -> List[StructuredEvidence]:
        return [e for e in self._parsed_evidence if e.confidence != ConfidenceLevel.UNRELIABLE]
