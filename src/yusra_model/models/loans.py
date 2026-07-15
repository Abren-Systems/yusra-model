"""Murabaha loan models and repayment schedule engine"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
import math
from typing import Optional


def _quarter_label(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"Q{q} {d.year}"


def _quarter_start(d: date) -> date:
    q = (d.month - 1) // 3 + 1
    return date(d.year, (q - 1) * 3 + 1, 1)


def _add_quarters(d: date, n: int) -> date:
    q = (d.month - 1) // 3 + 1
    y = d.year
    total_q = q + n
    y += (total_q - 1) // 4
    q = (total_q - 1) % 4 + 1
    return date(y, (q - 1) * 3 + 1, 1)


@dataclass
class Loan:
    supplier: str
    usd_value: float
    etb_principal: Optional[float]
    effective_rate: float
    start_date: date
    quarterly_repayment: Optional[float]
    tenor_quarters: int = 8
    profit_rate: float = 0.07

    def __post_init__(self):
        if self.etb_principal is None and self.usd_value:
            self.etb_principal = round(self.usd_value * self.effective_rate, 2)
        if self.quarterly_repayment is None and self.etb_principal:
            total_profit = round(self.etb_principal * (self.tenor_quarters / 4) * self.profit_rate, 2)
            self.quarterly_repayment = round(self.etb_principal / self.tenor_quarters + total_profit / self.tenor_quarters, 2)

    @property
    def total_profit(self) -> float:
        return round(self.etb_principal * (self.tenor_quarters / 4) * self.profit_rate, 2) if self.etb_principal else 0

    @property
    def total_cost(self) -> float:
        return round(self.etb_principal + self.total_profit, 2) if self.etb_principal else 0

    @property
    def profit_per_quarter(self) -> float:
        return round(self.total_profit / self.tenor_quarters, 2) if self.tenor_quarters else 0

    @property
    def principal_per_quarter(self) -> float:
        return round(self.quarterly_repayment - self.profit_per_quarter, 2) if self.quarterly_repayment else 0

    @property
    def start_quarter(self) -> str:
        return _quarter_label(self.start_date)

    def repayment_schedule(self, quarter_labels: list[str]) -> list[dict]:
        """Generate repayment entries for this loan."""
        sq = _quarter_label(_quarter_start(self.start_date))
        if sq not in quarter_labels:
            return []
        start_idx = quarter_labels.index(sq)
        entries = []
        for off in range(self.tenor_quarters):
            qi = start_idx + 1 + off
            if qi >= len(quarter_labels):
                break
            ql = quarter_labels[qi]
            remaining = round(self.total_cost - self.quarterly_repayment * (off + 1), 2)
            entries.append({
                "supplier": self.supplier,
                "usd_value": self.usd_value,
                "etb_principal": self.etb_principal,
                "start_date": self.start_date,
                "end_date": _add_quarters(self.start_date, self.tenor_quarters),
                "quarter": ql,
                "quarterly_repayment": self.quarterly_repayment,
                "profit_charge": self.profit_per_quarter,
                "principal_repayment": self.principal_per_quarter,
                "balance": remaining,
            })
        return entries


@dataclass
class Portfolio:
    """Collection of loans with calculation helpers."""
    loans: list[Loan]
    total_facility: float
    profit_rate: float

    @property
    def total_principal(self) -> float:
        return round(sum(l.etb_principal for l in self.loans), 2)

    @property
    def total_quarterly_repayment(self) -> float:
        return round(sum(l.quarterly_repayment for l in self.loans), 2)

    @property
    def total_profit(self) -> float:
        return round(sum(l.total_profit for l in self.loans), 2)

    @property
    def total_cost(self) -> float:
        return round(self.total_principal + self.total_profit, 2)

    def remaining_facility(self) -> float:
        return round(self.total_facility - self.total_principal, 2)

    def allocate_remaining(self):
        """Allocate remaining facility proportionally to loans without explicit principal."""
        fixed = [l for l in self.loans if l.etb_principal is not None and l.quarterly_repayment is not None]
        variable = [l for l in self.loans if l.etb_principal is None or l.quarterly_repayment is None]
        if not variable:
            return
        used = sum(l.etb_principal for l in fixed)
        remaining = self.total_facility - used
        total_usd = sum(l.usd_value for l in variable)
        if total_usd == 0:
            return
        for l in variable:
            share = remaining * l.usd_value / total_usd
            l.etb_principal = round(share, 2)
            total_profit = round(l.etb_principal * (l.tenor_quarters / 4) * self.profit_rate, 2)
            l.quarterly_repayment = round(l.etb_principal / l.tenor_quarters + total_profit / l.tenor_quarters, 2)

    def repayment_by_quarter(self, quarter_labels: list[str]) -> dict[str, float]:
        result = {q: 0.0 for q in quarter_labels}
        for l in self.loans:
            for entry in l.repayment_schedule(quarter_labels):
                q = entry["quarter"]
                if q in result:
                    result[q] += entry["quarterly_repayment"]
        return result

    def drawdown_by_quarter(self, quarter_labels: list[str]) -> dict[str, float]:
        result = {q: 0.0 for q in quarter_labels}
        for l in self.loans:
            sq = l.start_quarter
            if sq in result:
                result[sq] += l.etb_principal
        return result
