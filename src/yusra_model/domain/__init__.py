"""Business domain data objects — pure dataclasses, no computation logic."""
from .strategy import StrategicContext, BusinessTargets
from .revenue import RevenueDrivers, ProductLine, SeasonalityProfile, CustomerSegment
from .costs import CostStructure, COGSBreakdown, OperatingExpenses, OpExCategory, HeadcountPlan
from .capital import (EquityPosition, DebtFacility, DebtStructure, DepreciableAsset,
                       CapExPlan, FixedAssets, InventoryPolicy, ReceivablesPolicy,
                       PayablesPolicy, WorkingCapitalPolicy)
from .taxation import TaxSettings

__all__ = [
    "StrategicContext", "BusinessTargets",
    "RevenueDrivers", "ProductLine", "SeasonalityProfile", "CustomerSegment",
    "CostStructure", "COGSBreakdown", "OperatingExpenses", "OpExCategory", "HeadcountPlan",
    "EquityPosition", "DebtFacility", "DebtStructure", "DepreciableAsset",
    "CapExPlan", "FixedAssets", "InventoryPolicy", "ReceivablesPolicy",
    "PayablesPolicy", "WorkingCapitalPolicy",
    "TaxSettings",
]
