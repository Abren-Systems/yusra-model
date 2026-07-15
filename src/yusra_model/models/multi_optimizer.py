"""Multi-dimensional business optimizer — finds optimal configurations across growth, margin, WC, leverage, and tenor.

Sweeps parameter grids through the full three-statement projection engine,
applies constraints, ranks by composite score, and identifies Pareto frontiers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from copy import deepcopy
import itertools
import logging

from yusra_model.config.loader import Config
from yusra_model.engine.project import project_full
from yusra_model.engine.statements import FinancialProjection

logger = logging.getLogger(__name__)

DEFAULT_GRID: dict[str, list] = {
    "growth_multiplier": [0.5, 1.0, 1.5],
    "price_multiplier": [0.95, 1.0, 1.05],
    "wc_efficiency": [0.8, 1.0, 1.2],
    "leverage_multiplier": [0.75, 1.0, 1.25],
    "tenor_quarters": [4, 6, 8],
}

DEFAULT_CONSTRAINTS: dict[str, float] = {
    "min_dscr": 1.2,
    "min_cash": 0.0,
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "roe": 0.35,
    "revenue_cagr": 0.25,
    "min_dscr": 0.20,
    "total_throughput": 0.20,
}


@dataclass
class VariantResult:
    """A single configuration variant and its projection KPIs."""
    params: dict[str, Any]
    kpis: dict[str, float]
    feasible: bool
    constraint_violations: list[str]


@dataclass
class MultiOptimizerResult:
    """All variants plus analysis helpers."""
    variants: list[VariantResult]
    dimension_grid: dict[str, list]
    constraints: dict[str, float]
    objective_weights: dict[str, float]

    @property
    def feasible_variants(self) -> list[VariantResult]:
        return [v for v in self.variants if v.feasible]

    @property
    def n_feasible(self) -> int:
        return sum(1 for v in self.variants if v.feasible)

    def ranked(self, n: int = 10) -> list[VariantResult]:
        """Return top N feasible variants by normalized weighted composite score."""
        feasible = self.feasible_variants
        if not feasible:
            return []

        ranges: dict[str, float] = {}
        mins: dict[str, float] = {}
        for k in self.objective_weights:
            vals = [v.kpis.get(k, 0) for v in feasible]
            mins[k] = min(vals)
            rng = max(vals) - mins[k]
            ranges[k] = rng if rng > 0 else 1.0

        def composite(v: VariantResult) -> float:
            score = 0.0
            for k, w in self.objective_weights.items():
                if k in v.kpis:
                    norm = (v.kpis[k] - mins[k]) / ranges[k]
                    score += w * norm
            return score

        return sorted(feasible, key=composite, reverse=True)[:n]

    def pareto_front(self, obj_a: str, obj_b: str) -> list[VariantResult]:
        """Return variants on the Pareto frontier for two objectives (both maximized)."""
        feasible = self.feasible_variants
        if not feasible:
            return []
        sorted_v = sorted(feasible, key=lambda v: v.kpis.get(obj_a, 0), reverse=True)
        front: list[VariantResult] = []
        max_b = float("-inf")
        for v in sorted_v:
            b_val = v.kpis.get(obj_b, 0)
            if b_val > max_b:
                max_b = b_val
                front.append(v)
        return front


def compute_kpis(proj: FinancialProjection) -> dict[str, float]:
    """Extract summary KPIs from a full three-statement projection."""
    revs = [p.income.revenue for p in proj.periods]
    nis = [p.income.net_income for p in proj.periods]
    eqs = [p.balance.total_equity for p in proj.periods]
    debts = [p.balance.long_term_debt for p in proj.periods]
    cash_balances = [p.balance.cash for p in proj.periods]
    ebitdas = [p.income.ebitda for p in proj.periods]
    repayments = [p.cash_flow.repayments for p in proj.periods]
    interest = [p.income.interest_expense for p in proj.periods]
    drawdowns = [p.cash_flow.drawdowns for p in proj.periods]

    n_years = proj.horizon_years
    first_year_rev = sum(revs[:4]) if len(revs) >= 4 else sum(revs)
    last_year_rev = sum(revs[-4:]) if len(revs) >= 4 else sum(revs)
    cagr = (last_year_rev / first_year_rev) ** (1.0 / max(n_years, 1)) - 1.0 if first_year_rev > 0 else 0.0

    total_ni = sum(nis)
    avg_equity = sum(eqs) / max(len(eqs), 1)
    roe = total_ni / avg_equity if avg_equity != 0 else 0.0

    dscrs = []
    for i in range(len(proj.periods)):
        ds = repayments[i] + interest[i]
        if ds > 0:
            dscrs.append(ebitdas[i] / ds)
    min_dscr = min(dscrs) if dscrs else 99.0

    min_cash = min(cash_balances) if cash_balances else 0.0
    total_throughput = sum(drawdowns)

    avg_net_margin = (
        sum(nis[i] / revs[i] for i in range(len(revs)) if revs[i] > 0)
        / max(len(revs), 1)
    )

    final_de = debts[-1] / eqs[-1] if len(eqs) > 0 and eqs[-1] != 0 else 99.0

    total_assets_avg = sum(p.balance.total_assets for p in proj.periods) / max(len(proj.periods), 1)
    avg_roa = total_ni / total_assets_avg if total_assets_avg != 0 else 0.0

    last_year_ni = sum(nis[-4:]) if len(nis) >= 4 else sum(nis)

    return {
        "revenue_cagr": round(cagr, 4),
        "roe": round(roe, 4),
        "min_dscr": round(min_dscr, 2),
        "min_cash": round(min_cash, 0),
        "total_throughput": round(total_throughput, 0),
        "avg_net_margin": round(avg_net_margin, 4),
        "final_debt_to_equity": round(final_de, 2),
        "avg_roa": round(avg_roa, 4),
        "last_year_net_income": round(last_year_ni, 0),
    }


def apply_params(cfg: Config, params: dict) -> Config:
    """Deep-copy Config and apply variant parameter overrides."""
    c = deepcopy(cfg)
    growth_mult = params.get("growth_multiplier", 1.0)
    price_mult = params.get("price_multiplier", 1.0)
    wc_eff = params.get("wc_efficiency", 1.0)
    lev_mult = params.get("leverage_multiplier", 1.0)
    tenor = params.get("tenor_quarters")

    if c.revenue and c.revenue.product_lines:
        for pl in c.revenue.product_lines:
            pl.growth_rate *= growth_mult
            pl.avg_price *= price_mult

    if c.working_capital_policy:
        wc = c.working_capital_policy
        wc.receivables.dso_target = max(1, int(wc.receivables.dso_target * wc_eff))
        wc.payables.dpo_target = max(1, int(wc.payables.dpo_target * wc_eff))
        wc.inventory.finished_goods_days = max(1, int(wc.inventory.finished_goods_days * wc_eff))

    if lev_mult != 1.0:
        c.total_facility = round(c.total_facility * lev_mult, 0)
        if c.loans:
            for loan in c.loans:
                if loan.get("etb_principal") is not None:
                    loan["etb_principal"] = round(loan["etb_principal"] * lev_mult, 0)
                if loan.get("quarterly_repayment") is not None:
                    loan["quarterly_repayment"] = round(loan["quarterly_repayment"] * lev_mult, 0)

    if tenor is not None:
        c.loan_tenor_quarters = tenor

    return c


def check_constraints(kpis: dict, constraints: dict) -> tuple[bool, list[str]]:
    violations: list[str] = []
    for key, threshold in constraints.items():
        if key in kpis and kpis[key] < threshold:
            violations.append(f"{key}: {kpis[key]} < {threshold}")
    return len(violations) == 0, violations


def run_optimizer(
    cfg: Config,
    grid: Optional[dict[str, list]] = None,
    constraints: Optional[dict[str, float]] = None,
    objective_weights: Optional[dict[str, float]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> MultiOptimizerResult:
    """Run multi-dimensional grid search over config variants."""
    g = grid if grid is not None else DEFAULT_GRID
    cons = constraints or DEFAULT_CONSTRAINTS
    weights = objective_weights or DEFAULT_WEIGHTS

    keys = list(g.keys())
    value_lists = [g[k] for k in keys]
    total = 1
    for vl in value_lists:
        total *= len(vl)

    variants: list[VariantResult] = []

    for i, combo in enumerate(itertools.product(*value_lists)):
        params = dict(zip(keys, combo))

        try:
            variant_cfg = apply_params(cfg, params)
            proj = project_full(variant_cfg)

            if not proj.all_balanced():
                logger.warning("Variant %s: balance check failed", params)
                kpis = compute_kpis(proj)
                feasible = False
                violations = ["balance_check_failed"]
            else:
                kpis = compute_kpis(proj)
                feasible, violations = check_constraints(kpis, cons)

        except Exception as e:
            logger.warning("Variant %s failed: %s", params, e)
            kpis = {}
            feasible = False
            violations = [str(e)]

        variants.append(VariantResult(
            params=params,
            kpis=kpis,
            feasible=feasible,
            constraint_violations=violations,
        ))

        if progress_callback:
            progress_callback(i + 1, total)

    return MultiOptimizerResult(
        variants=variants,
        dimension_grid=g,
        constraints=cons,
        objective_weights=weights,
    )
