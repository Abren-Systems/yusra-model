"""Scenario engine — predefined modifier presets, multi-scenario runner."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging

from yusra_model.config.loader import Config
from yusra_model.engine.project import project_full
from yusra_model.engine.statements import FinancialProjection
from yusra_model.strategy.delta import apply_delta

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
    return apply_delta(cfg,
        growth_multiplier=mod.growth_multiplier,
        price_multiplier=mod.price_multiplier,
        wc_efficiency=mod.wc_efficiency,
        leverage_multiplier=mod.leverage_multiplier,
        cost_escalation_shift=mod.cost_escalation_shift,
        overhead_shift=mod.overhead_shift,
        bad_debt_shift=mod.bad_debt_shift,
    )


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
            from yusra_model.models.multi_optimizer import compute_kpis
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
