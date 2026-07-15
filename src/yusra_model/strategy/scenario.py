"""Scenario engine — predefined modifier presets, multi-scenario runner."""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Optional
import logging

from yusra_model.config.loader import Config
from yusra_model.engine.project import project_full
from yusra_model.engine.statements import FinancialProjection
from yusra_model.models.multi_optimizer import compute_kpis

logger = logging.getLogger(__name__)


@dataclass
class ScenarioModifier:
    """Delta adjustments applied on top of a base Config."""
    name: str
    label: str
    growth_multiplier: float = 1.0
    price_multiplier: float = 1.0
    wc_efficiency: float = 1.0
    leverage_multiplier: float = 1.0
    cost_escalation_shift: float = 0.0
    bad_debt_shift: float = 0.0
    overhead_shift: float = 0.0


SCENARIOS: dict[str, ScenarioModifier] = {
    "base": ScenarioModifier(name="base", label="Base Case"),
    "upside": ScenarioModifier(
        name="upside", label="Upside Case",
        growth_multiplier=1.30,
        price_multiplier=1.05,
        wc_efficiency=0.85,
    ),
    "downside": ScenarioModifier(
        name="downside", label="Downside Case",
        growth_multiplier=0.70,
        price_multiplier=0.95,
        wc_efficiency=1.15,
        cost_escalation_shift=0.02,
        bad_debt_shift=0.005,
        overhead_shift=0.10,
    ),
    "stress": ScenarioModifier(
        name="stress", label="Stress Case",
        growth_multiplier=0.50,
        price_multiplier=0.90,
        wc_efficiency=1.30,
        leverage_multiplier=0.75,
        cost_escalation_shift=0.05,
        bad_debt_shift=0.010,
        overhead_shift=0.20,
    ),
}


@dataclass
class ScenarioResult:
    name: str
    label: str
    kpis: dict[str, float]
    projection: FinancialProjection
    balanced: bool


def apply_modifier(cfg: Config, mod: ScenarioModifier) -> Config:
    """Apply a scenario modifier to a deep-copied Config."""
    c = deepcopy(cfg)

    # Growth & pricing
    if c.revenue and c.revenue.product_lines:
        for pl in c.revenue.product_lines:
            pl.growth_rate *= mod.growth_multiplier
            pl.avg_price *= mod.price_multiplier
        if mod.bad_debt_shift:
            c.revenue.bad_debt_rate = min(1.0, c.revenue.bad_debt_rate + mod.bad_debt_shift)

    # Working capital
    if c.working_capital_policy:
        wc = c.working_capital_policy
        wc.receivables.dso_target = max(1, int(wc.receivables.dso_target * mod.wc_efficiency))
        wc.payables.dpo_target = max(1, int(wc.payables.dpo_target * mod.wc_efficiency))
        wc.inventory.finished_goods_days = max(1, int(wc.inventory.finished_goods_days * mod.wc_efficiency))

    # Leverage
    if mod.leverage_multiplier != 1.0:
        c.total_facility = round(c.total_facility * mod.leverage_multiplier, 0)
        if c.loans:
            for loan in c.loans:
                if loan.get("etb_principal") is not None:
                    loan["etb_principal"] = round(loan["etb_principal"] * mod.leverage_multiplier, 0)
                if loan.get("quarterly_repayment") is not None:
                    loan["quarterly_repayment"] = round(loan["quarterly_repayment"] * mod.leverage_multiplier, 0)

    # Cost escalation
    if c.costs and mod.cost_escalation_shift:
        c.costs.escalation_rate = max(0.0, c.costs.escalation_rate + mod.cost_escalation_shift)

    # Overheads
    if mod.overhead_shift and c.costs and c.costs.operating_expenses:
        opex = c.costs.operating_expenses
        for cat in (opex.sales_marketing, opex.distribution, opex.admin, opex.r_and_d, opex.other):
            cat.fixed_per_month = round(cat.fixed_per_month * (1 + mod.overhead_shift), 2)

    return c


def run_scenarios(
    cfg: Config,
    scenario_names: Optional[list[str]] = None,
) -> list[ScenarioResult]:
    """Run one or more scenarios and return results with KPIs."""
    if scenario_names is None:
        scenario_names = list(SCENARIOS)

    results: list[ScenarioResult] = []
    for name in scenario_names:
        mod = SCENARIOS.get(name)
        if mod is None:
            logger.warning("Unknown scenario '%s', skipping", name)
            continue
        try:
            scenario_cfg = apply_modifier(cfg, mod)
            proj = project_full(scenario_cfg)
            kpis = compute_kpis(proj)
            results.append(ScenarioResult(
                name=name,
                label=mod.label,
                kpis=kpis,
                projection=proj,
                balanced=proj.all_balanced(),
            ))
        except Exception as e:
            logger.error("Scenario '%s' failed: %s", name, e)
            results.append(ScenarioResult(
                name=name,
                label=mod.label,
                kpis={},
                projection=FinancialProjection(),
                balanced=False,
            ))

    return results
