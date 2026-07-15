"""Capital structure — equity, debt facilities, fixed assets, working capital policies."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EquityPosition:
    paid_in_capital: float = 0.0
    retained_earnings: float = 0.0
    additional_paid_in: float = 0.0

    @property
    def total_equity(self) -> float:
        return self.paid_in_capital + self.retained_earnings + self.additional_paid_in


@dataclass
class DebtFacility:
    facility: float = 0.0
    type: str = "Murabaha_Revolving"
    profit_rate: float = 0.07
    tenor_quarters: int = 8
    purpose: str = ""
    outstanding: float = 0.0


@dataclass
class DebtStructure:
    facilities: list[DebtFacility] = field(default_factory=list)
    target_lt_debt_to_ebitda: float = 2.0
    target_debt_to_equity: float = 1.5
    max_dscr: float = 1.5


@dataclass
class DepreciableAsset:
    cost: float = 0.0
    accumulated_depreciation: float = 0.0
    useful_life_years: int = 10
    depreciation_method: str = "straight_line"
    description: str = ""


@dataclass
class CapExPlan:
    year_1: float = 0.0
    year_2: float = 0.0
    year_3: float = 0.0
    year_4: float = 0.0
    year_5: float = 0.0

    def for_year(self, offset: int) -> float:
        return [self.year_1, self.year_2, self.year_3, self.year_4, self.year_5][offset] if 0 <= offset < 5 else 0.0


@dataclass
class FixedAssets:
    existing_assets: list[DepreciableAsset] = field(default_factory=list)
    capex_plan: CapExPlan = field(default_factory=CapExPlan)


@dataclass
class InventoryPolicy:
    raw_materials_days: int = 45
    wip_days: int = 15
    finished_goods_days: int = 60
    safety_stock_days: int = 15
    obsolescence_rate: float = 0.02


@dataclass
class ReceivablesPolicy:
    dso_target: int = 30
    bad_debt_rate: float = 0.005


@dataclass
class PayablesPolicy:
    dpo_target: int = 45


@dataclass
class WorkingCapitalPolicy:
    inventory: InventoryPolicy = field(default_factory=InventoryPolicy)
    receivables: ReceivablesPolicy = field(default_factory=ReceivablesPolicy)
    payables: PayablesPolicy = field(default_factory=PayablesPolicy)
    cash_conversion_cycle_target: int = 60
