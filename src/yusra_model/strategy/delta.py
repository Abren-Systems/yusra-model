"""Shared Config-delta logic — eliminates duplication across optimizer, scenario, and sensitivity modules."""
from __future__ import annotations
from copy import deepcopy
from yusra_model.config.loader import Config


def apply_delta(
    cfg: Config,
    *,
    growth_multiplier: float = 1.0,
    price_multiplier: float = 1.0,
    wc_efficiency: float = 1.0,
    leverage_multiplier: float = 1.0,
    cost_escalation_shift: float = 0.0,
    overhead_shift: float = 0.0,
    bad_debt_shift: float = 0.0,
) -> Config:
    """Deep-copy Config and apply business-parameter deltas."""
    c = deepcopy(cfg)

    # Growth & pricing
    if c.revenue and c.revenue.product_lines:
        for pl in c.revenue.product_lines:
            pl.growth_rate *= growth_multiplier
            pl.avg_price *= price_multiplier
        if bad_debt_shift:
            c.revenue.bad_debt_rate = min(1.0, c.revenue.bad_debt_rate + bad_debt_shift)

    # Working capital
    if c.working_capital_policy:
        wc = c.working_capital_policy
        wc.receivables.dso_target = max(1, int(wc.receivables.dso_target * wc_efficiency))
        wc.payables.dpo_target = max(1, int(wc.payables.dpo_target * wc_efficiency))
        wc.inventory.finished_goods_days = max(1, int(wc.inventory.finished_goods_days * wc_efficiency))

    # Leverage
    if leverage_multiplier != 1.0:
        c.total_facility = round(c.total_facility * leverage_multiplier, 0)
        if c.loans:
            for loan in c.loans:
                if loan.get("etb_principal") is not None:
                    loan["etb_principal"] = round(loan["etb_principal"] * leverage_multiplier, 0)
                if loan.get("quarterly_repayment") is not None:
                    loan["quarterly_repayment"] = round(loan["quarterly_repayment"] * leverage_multiplier, 0)

    # Cost escalation
    if cost_escalation_shift and c.costs:
        c.costs.escalation_rate = max(0.0, c.costs.escalation_rate + cost_escalation_shift)

    # Overheads
    if overhead_shift and c.costs and c.costs.operating_expenses:
        opex = c.costs.operating_expenses
        for cat in (opex.sales_marketing, opex.distribution, opex.admin, opex.r_and_d, opex.other):
            cat.fixed_per_month = round(cat.fixed_per_month * (1 + overhead_shift), 2)

    return c
