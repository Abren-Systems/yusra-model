"""Sensitivity analysis — vary one driver at a time, show impact on KPIs."""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Optional
import logging

from yusra_model.config.loader import Config
from yusra_model.engine.project import project_full
from yusra_model.models.multi_optimizer import compute_kpis

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
    c = deepcopy(cfg)
    factor = 1 + change_pct / 100.0

    if driver == "growth":
        if c.revenue and c.revenue.product_lines:
            for pl in c.revenue.product_lines:
                pl.growth_rate *= factor

    elif driver == "price":
        if c.revenue and c.revenue.product_lines:
            for pl in c.revenue.product_lines:
                pl.avg_price *= factor

    elif driver == "wc":
        if c.working_capital_policy:
            wc = c.working_capital_policy
            wc.receivables.dso_target = max(1, int(wc.receivables.dso_target * factor))
            wc.payables.dpo_target = max(1, int(wc.payables.dpo_target * factor))
            wc.inventory.finished_goods_days = max(1, int(wc.inventory.finished_goods_days * factor))

    elif driver == "leverage":
        c.total_facility = round(c.total_facility * factor, 0)
        if c.loans:
            for loan in c.loans:
                if loan.get("etb_principal") is not None:
                    loan["etb_principal"] = round(loan["etb_principal"] * factor, 0)
                if loan.get("quarterly_repayment") is not None:
                    loan["quarterly_repayment"] = round(loan["quarterly_repayment"] * factor, 0)

    elif driver == "cost_escalation":
        if c.costs:
            c.costs.escalation_rate = max(0.0, c.costs.escalation_rate * factor)

    return c


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
