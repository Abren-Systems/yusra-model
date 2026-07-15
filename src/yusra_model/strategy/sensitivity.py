"""Sensitivity analysis — vary one driver at a time, show impact on KPIs."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import logging

from yusra_model.config.loader import Config
from yusra_model.engine.project import project_full
from yusra_model.strategy.delta import apply_delta

logger = logging.getLogger(__name__)

SENSITIVITY_DRIVERS = ["growth", "price", "wc", "leverage", "cost_escalation"]
SENSITIVITY_PCT = [-20, -10, 10, 20]
TARGET_KPIS = ["roe", "min_dscr", "last_year_net_income"]


@dataclass
class SensitivityPoint:
    driver: str
    change_pct: int
    kpis: dict[str, float]
    delta_kpis: dict[str, float]


@dataclass
class SensitivityResult:
    base_kpis: dict[str, float]
    points: list[SensitivityPoint]

    def for_driver(self, driver: str) -> list[SensitivityPoint]:
        return [p for p in self.points if p.driver == driver]


def _apply_driver(cfg: Config, driver: str, change_pct: int) -> Config:
    """Apply a percentage change to one driver in a deep-copied Config."""
    factor = 1 + change_pct / 100.0

    if driver == "growth":
        return apply_delta(cfg, growth_multiplier=factor)
    elif driver == "price":
        return apply_delta(cfg, price_multiplier=factor)
    elif driver == "wc":
        return apply_delta(cfg, wc_efficiency=factor)
    elif driver == "leverage":
        return apply_delta(cfg, leverage_multiplier=factor)
    elif driver == "cost_escalation":
        # cost_escalation_shift is additive; for sensitivity we want multiplicative
        base = cfg.costs.escalation_rate if cfg.costs else 0.08
        shift = base * (factor - 1)
        return apply_delta(cfg, cost_escalation_shift=shift)
    return deepcopy(cfg)


def run_sensitivity(
    cfg: Config,
    drivers: Optional[list[str]] = None,
    pct_changes: Optional[list[int]] = None,
    target_kpis: Optional[list[str]] = None,
) -> SensitivityResult:
    """Run sensitivity analysis by varying one driver at a time."""
    d_list = drivers or SENSITIVITY_DRIVERS
    pct_list = pct_changes or SENSITIVITY_PCT
    t_kpis = target_kpis or TARGET_KPIS

    # Base case
    base_proj = project_full(cfg)
    from yusra_model.models.multi_optimizer import compute_kpis
    base_kpis = compute_kpis(base_proj)

    points: list[SensitivityPoint] = []

    for driver in d_list:
        for pct in pct_list:
            try:
                mod_cfg = _apply_driver(cfg, driver, pct)
                proj = project_full(mod_cfg)
                kpis = compute_kpis(proj)
                deltas = {
                    k: round(kpis.get(k, 0) - base_kpis.get(k, 0), 4)
                    for k in t_kpis
                }
                points.append(SensitivityPoint(
                    driver=driver,
                    change_pct=pct,
                    kpis=kpis,
                    delta_kpis=deltas,
                ))
            except Exception as e:
                logger.warning("Sensitivity %s %d%% failed: %s", driver, pct, e)

    return SensitivityResult(base_kpis=base_kpis, points=points)
