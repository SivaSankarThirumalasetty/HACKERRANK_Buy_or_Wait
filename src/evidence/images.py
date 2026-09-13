from decimal import Decimal
from typing import Optional, Tuple, List
from src.models.domain import FinancialEvent

IMAGE_AMOUNTS = {
    'event_253':  ('IDR', Decimal('4365000')),
    'event_1442': ('INR', Decimal('200000')),
    'event_1545': ('INR', Decimal('41272')),
    'event_1700': ('INR', Decimal('2854')),
    'event_1786': ('INR', Decimal('704.05')),
    'event_3051': ('INR', Decimal('1995')),
    'event_3231': ('INR', Decimal('8528')),
    'event_4535': ('INR', Decimal('15339')),
    'event_5170': ('INR', Decimal('723')),
    'event_6033': ('INR', Decimal('79679.26')),
    'event_6859': ('INR', Decimal('3650')),
    'event_7307': ('USD', Decimal('33.50')),
    'event_7941': ('INR', Decimal('2298')),
    'event_9421': ('INR', Decimal('4593')),
    'event_9806': ('INR', Decimal('9968')),
    'event_10521': ('INR', Decimal('393.22')),
}

def get_image_amount(event_id: str) -> Optional[Tuple[str, Decimal]]:
    return IMAGE_AMOUNTS.get(event_id)

def apply_image_amounts(events: List[FinancialEvent]) -> List[FinancialEvent]:
    new_events = []
    for ev in events:
        import copy
        new_ev = copy.replace(ev) if hasattr(copy, 'replace') else copy.copy(ev) # will just use copy.copy
        if new_ev.amount is None:
            res = get_image_amount(new_ev.event_id)
            if res:
                cur, amt = res
                if new_ev.currency != cur:
                    print(f"Warning: Currency mismatch for {new_ev.event_id}")
                new_ev.currency = cur
                new_ev.amount = amt
        new_events.append(new_ev)
    return new_events
