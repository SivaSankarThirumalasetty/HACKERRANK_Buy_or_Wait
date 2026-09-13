from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class SpendingChange:
    action: str  # 'stop' or 'reduce_to'
    event_id: str
    new_amount: Optional[Decimal] = None

    def to_str(self) -> str:
        if self.action == 'stop':
            return f"stop:{self.event_id}"
        elif self.action == 'reduce_to':
            # e.g. reduce_to:event_989:665950 or reduce_to:event_1816:23.50
            if self.new_amount is not None:
                if self.new_amount % 1 == 0:
                    amt_str = str(int(self.new_amount))
                else:
                    amt_str = str(self.new_amount.quantize(Decimal('0.01')))
            else:
                amt_str = '0'
            return f"reduce_to:{self.event_id}:{amt_str}"
        return f"{self.action}:{self.event_id}"
