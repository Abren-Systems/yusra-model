"""Cost structure — COGS breakdown, operating expenses, headcount, escalations."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class COGSBreakdown:
    raw_materials_pct: float = 0.55
    import_duties_pct: float = 0.15
    freight_pct: float = 0.10
    direct_labor_pct: float = 0.10
    other_direct_pct: float = 0.10

    def __post_init__(self):
        total = self.raw_materials_pct + self.import_duties_pct + self.freight_pct + self.direct_labor_pct + self.other_direct_pct
        if abs(total - 1.0) > 0.01:
            factor = 1.0 / total
            self.raw_materials_pct *= factor
            self.import_duties_pct *= factor
            self.freight_pct *= factor
            self.direct_labor_pct *= factor
            self.other_direct_pct *= factor


@dataclass
class OpExCategory:
    fixed_per_month: float = 0.0
    variable_pct_of_revenue: float = 0.0
    description: str = ""


@dataclass
class OperatingExpenses:
    sales_marketing: OpExCategory = field(default_factory=OpExCategory)
    distribution: OpExCategory = field(default_factory=OpExCategory)
    admin: OpExCategory = field(default_factory=OpExCategory)
    r_and_d: OpExCategory = field(default_factory=OpExCategory)
    other: OpExCategory = field(default_factory=OpExCategory)


@dataclass
class HeadcountPlan:
    total_headcount: int = 0
    avg_cost_per_employee_per_month: float = 0.0
    hiring_growth_rate: float = 0.0  # annual headcount growth
    salary_escalation_rate: float = 0.0  # annual per-employee cost increase


@dataclass
class CostStructure:
    cogs_breakdown: COGSBreakdown = field(default_factory=COGSBreakdown)
    operating_expenses: OperatingExpenses = field(default_factory=OperatingExpenses)
    headcount: HeadcountPlan = field(default_factory=HeadcountPlan)
    escalation_rate: float = 0.08  # general cost inflation
    other_fixed_costs_per_month: float = 0.0
