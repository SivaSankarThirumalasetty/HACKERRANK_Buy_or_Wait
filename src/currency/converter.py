from decimal import Decimal
from datetime import date
from typing import List, Dict, Optional
from collections import defaultdict
import bisect

class ExchangeRateTable:
    def __init__(self, rates: List[Dict]):
        self.rates_lookup = defaultdict(list)
        for r in rates:
            if r['date'] and r['rate']:
                pair = (r['from_currency'], r['to_currency'])
                self.rates_lookup[pair].append((r['date'], r['rate']))
        
        for pair in self.rates_lookup:
            self.rates_lookup[pair].sort(key=lambda x: x[0])

    def get_rate(self, from_currency: str, to_currency: str, as_of_date: date) -> Decimal:
        if from_currency == to_currency:
            return Decimal('1')
        
        # Helper to find rate in direct pair
        def find_rate(fc, tc):
            pair = (fc, tc)
            if pair in self.rates_lookup:
                dates = [x[0] for x in self.rates_lookup[pair]]
                idx = bisect.bisect_right(dates, as_of_date)
                if idx > 0:
                    return self.rates_lookup[pair][idx - 1][1]
            return None

        # Direct
        rate = find_rate(from_currency, to_currency)
        if rate is not None:
            return rate
            
        # Inverse
        inv_rate = find_rate(to_currency, from_currency)
        if inv_rate is not None:
            return Decimal('1') / inv_rate

        # Multi-hop via USD
        rate_to_usd = find_rate(from_currency, 'USD') or (Decimal('1') / find_rate('USD', from_currency) if find_rate('USD', from_currency) else None)
        rate_usd_to_target = find_rate('USD', to_currency) or (Decimal('1') / find_rate(to_currency, 'USD') if find_rate(to_currency, 'USD') else None)
        
        if rate_to_usd is not None and rate_usd_to_target is not None:
            return rate_to_usd * rate_usd_to_target
            
        # Multi-hop via EUR
        rate_to_eur = find_rate(from_currency, 'EUR') or (Decimal('1') / find_rate('EUR', from_currency) if find_rate('EUR', from_currency) else None)
        rate_eur_to_target = find_rate('EUR', to_currency) or (Decimal('1') / find_rate(to_currency, 'EUR') if find_rate(to_currency, 'EUR') else None)

        if rate_to_eur is not None and rate_eur_to_target is not None:
            return rate_to_eur * rate_eur_to_target

        # Multi-hop via USD then EUR
        if rate_to_usd is not None:
            usd_to_eur = find_rate('USD', 'EUR') or (Decimal('1') / find_rate('EUR', 'USD') if find_rate('EUR', 'USD') else None)
            if usd_to_eur is not None and rate_eur_to_target is not None:
                return rate_to_usd * usd_to_eur * rate_eur_to_target

        # Multi-hop via EUR then USD
        if rate_to_eur is not None:
            eur_to_usd = find_rate('EUR', 'USD') or (Decimal('1') / find_rate('USD', 'EUR') if find_rate('USD', 'EUR') else None)
            if eur_to_usd is not None and rate_usd_to_target is not None:
                return rate_to_eur * eur_to_usd * rate_usd_to_target

        raise ValueError(f"No exchange rate found for {from_currency} to {to_currency} on {as_of_date}")

    def convert(self, amount: Decimal, from_currency: str, to_currency: str, as_of_date: date) -> Decimal:
        if from_currency == to_currency:
            return amount
        rate = self.get_rate(from_currency, to_currency, as_of_date)
        return amount * rate

    def to_home_currency(self, amount: Decimal, event_currency: str, home_currency: str, as_of_date: date) -> Decimal:
        return self.convert(amount, event_currency, home_currency, as_of_date)
