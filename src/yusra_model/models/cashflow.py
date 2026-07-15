"""Cash flow projection engine — dual sales cycles in parallel"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .loans import Portfolio


QUARTER_LABELS = [f"Q{q} {yr}" for yr in range(2026, 2029) for q in range(1, 5)]
QUARTER_LABELS = QUARTER_LABELS[QUARTER_LABELS.index("Q2 2026"):QUARTER_LABELS.index("Q4 2028") + 1]


@dataclass
class CashFlowRow:
    quarter: str
    opening_cash: float = 0.0
    drawdowns: float = 0.0
    repayments: float = 0.0
    sales_inflow: float = 0.0
    overheads: float = 0.0
    net_cash_flow: float = 0.0
    closing_cash: float = 0.0
    closing_inventory: float = 0.0
    facility_util_pct: float = 0.0


@dataclass
class CycleProjection:
    cycle_name: str
    rows: list[CashFlowRow] = field(default_factory=list)
    quarter_labels: list[str] = field(default_factory=lambda: QUARTER_LABELS)

    def to_dicts(self) -> list[dict]:
        return [r.__dict__ for r in self.rows]


@dataclass
class CashFlowProjection:
    proj_3m: CycleProjection
    proj_6m: CycleProjection
    quarter_labels: list[str] = field(default_factory=lambda: QUARTER_LABELS)

    def select_cycle(self, cycle: str) -> CycleProjection:
        use_3m = cycle in ("3 Months", "3m")
        return self.proj_3m if use_3m else self.proj_6m

    @property
    def rows(self) -> list[CashFlowRow]:
        return self.proj_3m.rows

    def to_dicts(self) -> list[dict]:
        return self.proj_3m.to_dicts()


def _project_single_cycle(
    cycle_name: str,
    portfolio: Portfolio,
    opening_cash: float,
    opening_inventory: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
    sell_fraction: float,
) -> CycleProjection:
    """
    Run projection for one sales cycle.

    sell_fraction: fraction of available inventory sold per quarter
                   (1.0 for 3-month, 0.5 for 6-month cycle).
    """
    qlabels = QUARTER_LABELS
    drawdowns = portfolio.drawdown_by_quarter(qlabels)
    repayments = portfolio.repayment_by_quarter(qlabels)

    proj = CycleProjection(cycle_name=cycle_name)

    inv = opening_inventory
    cumulative_drawdowns = 0.0
    cumulative_repayments = 0.0

    for qi, q in enumerate(qlabels):
        dd = drawdowns.get(q, 0.0)
        rp = repayments.get(q, 0.0)
        oh = overheads_per_quarter
        cum_draw = cumulative_drawdowns + dd
        cum_repay = cumulative_repayments + rp

        # Inventory and sales
        avail = inv + dd
        is_last = qi >= len(qlabels) - 1
        cogs = avail if is_last else round(avail * sell_fraction, 2)
        rev = round(cogs * (1 + gross_profit_margin), 2)
        inv = round(avail - cogs, 2)

        ncf = round(dd - rp + rev - oh, 2)

        outstanding = max(0, round(cum_draw - cum_repay, 2))
        util_pct = round(outstanding / portfolio.total_facility, 4) if portfolio.total_facility else 0

        row = CashFlowRow(
            quarter=q,
            drawdowns=round(dd, 2),
            repayments=round(rp, 2),
            sales_inflow=rev,
            overheads=oh,
            closing_inventory=inv,
            facility_util_pct=util_pct,
        )

        if qi == 0:
            row.opening_cash = opening_cash
        else:
            row.opening_cash = proj.rows[qi - 1].closing_cash

        row.net_cash_flow = ncf
        row.closing_cash = round(row.opening_cash + ncf, 2)

        proj.rows.append(row)
        cumulative_drawdowns = cum_draw
        cumulative_repayments = cum_repay

    return proj


def project(
    portfolio: Portfolio,
    opening_cash: float,
    opening_inventory: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
) -> CashFlowProjection:
    """Run the full cash flow projection for both sales cycles in parallel."""
    proj_3m = _project_single_cycle(
        "3 Months", portfolio, opening_cash, opening_inventory,
        overheads_per_quarter, gross_profit_margin, sell_fraction=1.0,
    )
    proj_6m = _project_single_cycle(
        "6 Months", portfolio, opening_cash, opening_inventory,
        overheads_per_quarter, gross_profit_margin, sell_fraction=0.5,
    )
    return CashFlowProjection(proj_3m=proj_3m, proj_6m=proj_6m)


def select_cycle(proj: CashFlowProjection, cycle: str) -> CycleProjection:
    """Return the projection for the selected sales cycle."""
    return proj.select_cycle(cycle)
