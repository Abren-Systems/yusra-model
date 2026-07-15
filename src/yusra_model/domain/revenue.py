"""Revenue drivers — product lines, pricing, seasonality, customer segments."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProductLine:
    name: str
    base_volume: float = 0.0
    avg_price: float = 0.0
    growth_rate: float = 0.0
    cogs_per_unit: float = 0.0
    gross_margin: float = 0.0
    description: str = ""


@dataclass
class SeasonalityProfile:
    q1: float = 0.25
    q2: float = 0.25
    q3: float = 0.25
    q4: float = 0.25

    def __post_init__(self):
        total = self.q1 + self.q2 + self.q3 + self.q4
        if abs(total - 1.0) > 0.01:
            factor = 1.0 / total
            self.q1 *= factor
            self.q2 *= factor
            self.q3 *= factor
            self.q4 *= factor

    def for_quarter(self, q: int) -> float:
        return [self.q1, self.q2, self.q3, self.q4][q % 4]


@dataclass
class CustomerSegment:
    name: str
    revenue_pct: float = 0.0
    payment_terms_days: int = 30
    bad_debt_rate: float = 0.005


@dataclass
class RevenueDrivers:
    product_lines: list[ProductLine] = field(default_factory=list)
    seasonality: SeasonalityProfile = field(default_factory=SeasonalityProfile)
    cash_ratio: float = 0.85
    credit_ratio: float = 0.15
    credit_terms_days: int = 30
    bad_debt_rate: float = 0.005
    customer_segments: list[CustomerSegment] = field(default_factory=list)
