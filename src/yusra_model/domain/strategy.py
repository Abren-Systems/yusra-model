"""Strategic context, business targets, and planning parameters."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BusinessTargets:
    revenue_growth_annual: float = 0.15
    gross_margin: float = 0.28
    operating_margin: float = 0.12
    net_margin: float = 0.08
    roe: float = 0.25
    roic: float = 0.20
    dscr: float = 1.5
    current_ratio: float = 2.0
    lt_debt_to_ebitda: float = 2.0
    debt_to_equity: float = 1.5
    dividend_payout_ratio: float = 0.30
    cash_conversion_cycle_days: int = 60
    inventory_turns: float = 6.0


@dataclass
class StrategicContext:
    mission: str = ""
    planning_horizon_years: int = 5
    base_year: int = 2025
    targets: BusinessTargets = field(default_factory=BusinessTargets)
