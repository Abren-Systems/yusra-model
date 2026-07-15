"""Cash flow projection engine"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from .loans import Portfolio


QUARTER_LABELS = [f"Q{q} {yr}" for yr in range(2026, 2029) for q in range(1, 5)]
QUARTER_LABELS = QUARTER_LABELS[QUARTER_LABELS.index("Q2 2026"):QUARTER_LABELS.index("Q4 2028") + 1]


@dataclass
class CashFlowRow:
    quarter: str
    opening_cash: float = 0.0
    drawdowns: float = 0.0
    repayments: float = 0.0
    sales_inflow_3m: float = 0.0
    sales_inflow_6m: float = 0.0
    overheads: float = 0.0
    net_cash_flow: float = 0.0
    closing_cash: float = 0.0
    closing_inventory: float = 0.0
    facility_util_pct: float = 0.0


@dataclass
class CashFlowProjection:
    rows: list[CashFlowRow] = field(default_factory=list)
    quarter_labels: list[str] = field(default_factory=lambda: QUARTER_LABELS)

    def to_dicts(self) -> list[dict]:
        return [r.__dict__ for r in self.rows]


def project(
    portfolio: Portfolio,
    opening_cash: float,
    opening_inventory: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
) -> CashFlowProjection:
    """Run the full cash flow projection for all quarters."""
    qlabels = QUARTER_LABELS
    drawdowns = portfolio.drawdown_by_quarter(qlabels)
    repayments = portfolio.repayment_by_quarter(qlabels)

    proj = CashFlowProjection()

    # Inventory modelling: 3-month and 6-month sales cycles
    # 3-month: all available inventory sells within the quarter
    # 6-month: half sells each quarter

    inv_3m = opening_inventory
    inv_6m = opening_inventory
    cumulative_drawdowns = 0.0
    cumulative_repayments = 0.0

    for qi, q in enumerate(qlabels):
        dd = drawdowns.get(q, 0.0)
        rp = repayments.get(q, 0.0)
        oh = overheads_per_quarter
        cum_draw = cumulative_drawdowns + dd
        cum_repay = cumulative_repayments + rp

        # 3-month sales
        avail_3m = inv_3m + dd
        cogs_3m = avail_3m
        rev_3m = round(cogs_3m * (1 + gross_profit_margin), 2)
        inv_3m = 0.0

        # 6-month sales
        avail_6m = inv_6m + dd
        cogs_6m = avail_6m / 2 if qi < len(qlabels) - 1 else avail_6m
        rev_6m = round(cogs_6m * (1 + gross_profit_margin), 2)
        inv_6m = round(avail_6m - cogs_6m, 2)

        # Net cash flow depends on sales cycle
        ncf_3m = round(dd - rp + rev_3m - oh, 2)
        ncf_6m = round(dd - rp + rev_6m - oh, 2)

        row = CashFlowRow(
            quarter=q,
            drawdowns=round(dd, 2),
            repayments=round(rp, 2),
            sales_inflow_3m=rev_3m,
            sales_inflow_6m=rev_6m,
            overheads=oh,
        )

        # Opening/closing cash will be filled after
        # Facility utilisation
        outstanding = round(cum_draw - cum_repay, 2)
        row.facility_util_pct = round(outstanding / portfolio.total_facility, 4) if portfolio.total_facility else 0

        # Inventory after 3m cycle
        row.closing_inventory = round(inv_3m, 2)

        proj.rows.append(row)
        cumulative_drawdowns = cum_draw
        cumulative_repayments = cum_repay

    # Fill cash balances
    for qi, row in enumerate(proj.rows):
        if qi == 0:
            row.opening_cash = opening_cash
        else:
            row.opening_cash = proj.rows[qi - 1].closing_cash

        # Net cash flow placeholder — actual depends on cycle choice
        # Store both possibilities
        row.net_cash_flow = round(row.drawdowns - row.repayments + row.sales_inflow_3m - row.overheads, 2)
        row.closing_cash = round(row.opening_cash + row.net_cash_flow, 2)

    return proj


def select_cycle(proj: CashFlowProjection, cycle: str) -> CashFlowProjection:
    """Return a copy with the selected sales cycle's cash flows applied."""
    import copy
    result = copy.deepcopy(proj)
    use_3m = cycle == "3 Months" or cycle == "3m"
    for qi, row in enumerate(result.rows):
        sales = row.sales_inflow_3m if use_3m else row.sales_inflow_6m
        row.net_cash_flow = round(row.drawdowns - row.repayments + sales - row.overheads, 2)
        if qi == 0:
            row.opening_cash = proj.rows[qi].opening_cash
        else:
            row.opening_cash = result.rows[qi - 1].closing_cash
        row.closing_cash = round(row.opening_cash + row.net_cash_flow, 2)

        # Recalculate inventory for selected cycle
        if use_3m:
            row.closing_inventory = 0.0  # all sold in 3m
        # 6m inventory already computed in project()
    return result
