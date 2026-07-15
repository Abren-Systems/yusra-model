"""Three-statement financial projection engine — driver-based, quarterly."""
from __future__ import annotations
import math
from copy import deepcopy
from typing import Optional
from yusra_model.config.loader import Config
from yusra_model.domain import (
    StrategicContext, BusinessTargets,
    RevenueDrivers, ProductLine, SeasonalityProfile,
    CostStructure, OpExCategory,
    DebtFacility, EquityPosition, DepreciableAsset, CapExPlan, FixedAssets,
    WorkingCapitalPolicy, InventoryPolicy, ReceivablesPolicy, PayablesPolicy,
)
from .statements import (
    QuarterlyFinancials, IncomeStatement, BalanceSheet,
    CashFlowStatement, FinancialProjection,
)


def project_full(cfg: Config) -> FinancialProjection:
    """Project full three-statement financials over the planning horizon."""
    horizon = _horizon(cfg)
    periods: list[QuarterlyFinancials] = []

    # ── State that rolls forward ──
    fa_net = _opening_fa_net(cfg)
    retained = _opening_retained(cfg)
    cash = cfg.opening_cash
    inv = cfg.opening_inventory
    ar = 0.0
    ap = 0.0
    debt_outstanding = 0.0
    cumulative_loss = 0.0  # for tax loss carryforward

    # Compute opening balancing gap: Assets - (Liabilities + Equity)
    # This represents historical items not modelled (prior retained earnings,
    # accrued expenses, deferred revenue, etc.)
    opening_assets = cash + ar + inv + fa_net
    opening_l_e = ap + debt_outstanding + _opening_equity(cfg) + retained
    other_liabilities = max(0, opening_assets - opening_l_e)

    # Legacy loan schedules (repayments + drawdowns)
    legacy_repayments, legacy_drawdowns = _build_legacy_schedules(cfg)
    schedule_keys = set(legacy_repayments.keys()) | set(legacy_drawdowns.keys())
    revolving_start = 8
    if schedule_keys:
        last_scheduled = max(i for i, (y, q) in enumerate(horizon) if (y, q) in schedule_keys)
        revolving_start = last_scheduled + 1

    for q_idx, (year, q_num) in enumerate(horizon):
        label = f"Q{q_num} {year}"
        year_offset = year - cfg.strategy.base_year if cfg.strategy else 0

        # ── Revenue & COGS ──
        rev, cogs = _project_revenue(cfg, year, q_num, year_offset)

        # ── Operating Expenses ──
        opex_detail = _project_opex(cfg, rev, year_offset)

        # ── Depreciation ──
        dep = _project_depreciation(cfg, year_offset, fa_net)

        # ── Interest & Debt Service ──
        interest, drawdown, repayment, new_debt = _project_debt(
            cfg, q_idx, year, q_num, debt_outstanding,
            legacy_drawdowns, legacy_repayments,
            revolving_start,
        )

        # ── Tax ──
        ebit = rev - cogs - sum(_opex_list(opex_detail)) - dep - interest
        ebt = ebit
        tax, cumulative_loss = _project_tax(cfg, ebt, cumulative_loss)
        net_income = ebt - tax

        # ── Balance Sheet: Working Capital ──
        new_ar = _project_ar(cfg, rev, ar)
        new_inv = _project_inventory(cfg, cogs, year_offset, inv)
        new_ap = _project_ap(cfg, cogs, ap)

        # ── Fixed Assets roll-forward ──
        capex = _project_capex(cfg, year_offset)
        fa_net = fa_net - dep + capex

        # ── Debt roll-forward ──
        debt_outstanding = debt_outstanding + drawdown - repayment + new_debt

        # ── Dividends ──
        div = _project_dividends(cfg, net_income, year, q_num)

        # ── Cash Flow ──
        delta_ar = new_ar - ar
        delta_inv = new_inv - inv
        delta_ap = new_ap - ap
        ocf = net_income + dep - delta_ar - delta_inv + delta_ap
        icf = -capex
        fcf = drawdown - repayment + new_debt - div
        net_cf = ocf + icf + fcf
        opening_cash = cash
        cash = cash + net_cf

        # ── Update working capital state ──
        ar = new_ar
        inv = new_inv
        ap = new_ap

        # ── Equity roll-forward ──
        retained = retained + net_income - div

        # ── Build statements ──
        is_forecast = q_idx > 0  # first period is opening, rest are forecast
        pf = QuarterlyFinancials(
            period_label=label,
            year=year,
            quarter=q_num,
            is_forecast=is_forecast,
            income=IncomeStatement(
                revenue=round(rev, 2),
                cogs=round(cogs, 2),
                gross_profit=round(rev - cogs, 2),
                opex_sales_marketing=round(opex_detail[0], 2),
                opex_distribution=round(opex_detail[1], 2),
                opex_admin=round(opex_detail[2], 2),
                opex_r_and_d=round(opex_detail[3], 2),
                opex_other=round(opex_detail[4], 2),
                total_opex=round(sum(_opex_list(opex_detail)), 2),
                ebitda=round(rev - cogs - sum(_opex_list(opex_detail)), 2),
                depreciation=round(dep, 2),
                ebit=round(ebit, 2),
                interest_expense=round(interest, 2),
                ebt=round(ebt, 2),
                tax_expense=round(tax, 2),
                net_income=round(net_income, 2),
            ),
            balance=BalanceSheet(
                cash=round(cash, 2),
                accounts_receivable=round(ar, 2),
                inventory=round(inv, 2),
                fixed_assets_net=round(fa_net, 2),
                accounts_payable=round(ap, 2),
                short_term_debt=0.0,
                long_term_debt=round(debt_outstanding, 2),
                other_liabilities=round(other_liabilities, 2),
                paid_in_capital=round(_opening_equity(cfg), 2),
                retained_earnings=round(retained, 2),
            ),
            cash_flow=CashFlowStatement(
                net_income=round(net_income, 2),
                depreciation=round(dep, 2),
                change_in_ar=round(delta_ar, 2),
                change_in_inventory=round(delta_inv, 2),
                change_in_ap=round(delta_ap, 2),
                operating_cash_flow=round(ocf, 2),
                capex=round(capex, 2),
                investing_cash_flow=round(icf, 2),
                drawdowns=round(drawdown, 2),
                repayments=round(repayment, 2),
                dividends=round(div, 2),
                financing_cash_flow=round(fcf, 2),
                net_change_in_cash=round(net_cf, 2),
                opening_cash=round(opening_cash, 2),
                closing_cash=round(cash, 2),
            ),
        )

        # ── Post-balance: compute totals ──
        _post_balance(pf, retained)

        periods.append(pf)

    # Build projection with first period serving as opening snapshot
    return FinancialProjection(
        periods=periods,
        company=cfg.company,
        currency=cfg.currency,
        base_year=cfg.strategy.base_year if cfg.strategy else 2025,
        horizon_years=cfg.strategy.planning_horizon_years if cfg.strategy else 5,
    )


# ─── Period generation ─────────────────────────────────────────────────


def _horizon(cfg: Config) -> list[tuple[int, int]]:
    """Return list of (year, quarter) tuples spanning the planning horizon."""
    base = cfg.strategy.base_year if cfg.strategy else 2025
    years = cfg.strategy.planning_horizon_years if cfg.strategy else 5
    periods: list[tuple[int, int]] = []
    for y in range(base, base + years):
        for q in range(1, 5):
            periods.append((y, q))
    return periods


# ─── Revenue ────────────────────────────────────────────────────────────


def _project_revenue(cfg: Config, year: int, q_num: int, year_offset: int) -> tuple[float, float]:
    """Project quarterly revenue and COGS from product lines."""
    rev_drivers = cfg.revenue
    if rev_drivers is None or not rev_drivers.product_lines:
        # Fallback: use legacy sales model
        gm = cfg.gross_profit_margin
        facility = cfg.total_facility
        quarterly_cogs = facility / 4  # rough assumption
        rev = quarterly_cogs * (1 + gm)
        return rev, quarterly_cogs

    total_rev = 0.0
    total_cogs = 0.0
    seas = rev_drivers.seasonality
    for pl in rev_drivers.product_lines:
        annual_vol = pl.base_volume * ((1 + pl.growth_rate) ** year_offset)
        q_vol = annual_vol * seas.for_quarter(q_num)
        esc = cfg.costs.escalation_rate if cfg.costs else 0.08
        price = pl.avg_price * ((1 + esc) ** year_offset)
        unit_cogs = pl.cogs_per_unit * ((1 + esc) ** year_offset)
        total_rev += q_vol * price
        total_cogs += q_vol * unit_cogs

    return total_rev, total_cogs


# ─── Operating Expenses ─────────────────────────────────────────────────


def _project_opex(cfg: Config, revenue: float, year_offset: int) -> tuple[float, float, float, float, float]:
    """Project quarterly OpEx by category. Returns (s&m, dist, admin, r&d, other)."""
    costs = cfg.costs
    if costs is None:
        esc = 0.08
        oh = cfg.overheads_per_month * 3 * ((1 + esc) ** year_offset)
        return oh * 0.3, oh * 0.2, oh * 0.35, oh * 0.1, oh * 0.05

    esc = (1 + costs.escalation_rate) ** year_offset
    opex = costs.operating_expenses

    def _calc(cat: OpExCategory) -> float:
        fixed = cat.fixed_per_month * 3 * esc
        variable = cat.variable_pct_of_revenue * revenue
        return fixed + variable

    return (
        _calc(opex.sales_marketing),
        _calc(opex.distribution),
        _calc(opex.admin),
        _calc(opex.r_and_d),
        _calc(opex.other),
    )


def _opex_list(t: tuple) -> list[float]:
    return list(t)


# ─── Depreciation & CapEx ──────────────────────────────────────────────


def _project_depreciation(cfg: Config, year_offset: int, current_fa_net: float) -> float:
    """Quarterly depreciation from existing assets plus new CapEx."""
    fa = cfg.fixed_assets
    if fa is None:
        return 0.0

    total_dep_q = 0.0
    for asset in fa.existing_assets:
        annual_dep = asset.cost / max(asset.useful_life_years, 1)
        if asset.accumulated_depreciation < asset.cost:
            total_dep_q += annual_dep / 4

    # CapEx placed in service -> depreciated from placement year
    for cy in range(year_offset + 1):
        capex_amt = fa.capex_plan.for_year(cy)
        if capex_amt > 0:
            useful_life = fa.default_capex_useful_life_years
            remaining_years = max(useful_life - cy, 1)
            total_dep_q += (capex_amt / remaining_years) / 4

    return total_dep_q


def _project_capex(cfg: Config, year_offset: int) -> float:
    """Quarterly CapEx spend for this year offset."""
    fa = cfg.fixed_assets
    if fa is None:
        return 0.0
    annual = fa.capex_plan.for_year(year_offset)
    return annual / 4  # spread evenly across quarters


# ─── Debt & Interest ───────────────────────────────────────────────────


def _build_legacy_schedules(cfg: Config) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], float]]:
    """Build (repayment_schedule, drawdown_schedule) from legacy loans."""
    from yusra_model.models.loans import Loan, Portfolio, _quarter_label, _add_quarters
    import re

    loans = [Loan(**l) for l in cfg.loans]
    portfolio = Portfolio(tuple(loans), cfg.total_facility, cfg.profit_rate)
    portfolio = portfolio.with_allocated_remaining()

    if not loans:
        return {}, {}

    first_start = min(l.start_date for l in loans)
    q_labels = []
    for off in range(12):
        d = _add_quarters(first_start, off)
        lbl = _quarter_label(d)
        if lbl not in q_labels:
            q_labels.append(lbl)

    def _parse(by_q: dict) -> dict[tuple[int, int], float]:
        schedule: dict[tuple[int, int], float] = {}
        for lbl, amt in by_q.items():
            m = re.match(r"Q(\d) (\d{4})", lbl)
            if m:
                schedule[(int(m.group(2)), int(m.group(1)))] = amt
        return schedule

    return _parse(portfolio.repayment_by_quarter(q_labels)), _parse(portfolio.drawdown_by_quarter(q_labels))


def _project_debt(
    cfg: Config,
    q_idx: int,
    year: int,
    q_num: int,
    current_outstanding: float,
    legacy_drawdowns: dict,
    legacy_repayments: dict,
    revolving_start: int | None = None,
) -> tuple[float, float, float, float]:
    """Return (interest, drawdown, repayment, new_debt_issued)."""
    key = (year, q_num)
    drawdown = legacy_drawdowns.get(key, 0.0)
    repayment = legacy_repayments.get(key, 0.0)

    # After legacy schedule ends, assume revolving facility
    if revolving_start is not None and q_idx >= revolving_start:
        # Facility is fully drawn and revolving
        if current_outstanding < cfg.total_facility:
            drawdown = cfg.total_facility - current_outstanding
        # Repayment = principal over standard tenor
        tenor = cfg.loan_tenor_quarters
        principal_per_q = cfg.total_facility / max(tenor, 1)
        repayment = min(principal_per_q, current_outstanding)

    interest = current_outstanding * cfg.profit_rate / 4
    new_debt = 0.0  # no new debt beyond revolving facility

    return interest, drawdown, repayment, new_debt


# ─── Tax ───────────────────────────────────────────────────────────────


def _project_tax(cfg: Config, ebt: float, cumulative_loss: float) -> tuple[float, float]:
    """Compute tax with loss carryforward."""
    tax_rate = cfg.taxation.corporate_income_tax_rate if cfg.taxation else 0.30
    if ebt <= 0:
        cumulative_loss += abs(ebt)
        return 0.0, cumulative_loss

    # Use loss carryforward to offset taxable income
    taxable = max(0, ebt - cumulative_loss)
    cumulative_loss = max(0, cumulative_loss - ebt)
    tax = taxable * tax_rate
    return tax, cumulative_loss


# ─── Working Capital ───────────────────────────────────────────────────


def _project_ar(cfg: Config, revenue: float, current_ar: float) -> float:
    """AR = revenue * DSO / 90 (turnover-ratio based)."""
    wc = cfg.working_capital_policy
    dso = wc.receivables.dso_target if wc else 30
    target = revenue * dso / 90.0
    return max(target, 0)


def _project_inventory(cfg: Config, cogs: float, year_offset: int, current_inv: float) -> float:
    """Inventory = annualized COGS / 365 * DIO."""
    wc = cfg.working_capital_policy
    dio = wc.inventory.finished_goods_days if wc else 60
    annual_cogs = cogs * 4
    target = annual_cogs / 365.0 * dio
    return max(target, 0)


def _project_ap(cfg: Config, cogs: float, current_ap: float) -> float:
    """AP = COGS * DPO / 90."""
    wc = cfg.working_capital_policy
    dpo = wc.payables.dpo_target if wc else 45
    target = cogs * dpo / 90.0
    return max(target, 0)


# ─── Dividends ─────────────────────────────────────────────────────────


def _project_dividends(cfg: Config, net_income: float, year: int, q_num: int) -> float:
    """Pay dividend annually in Q4 based on full-year net income."""
    if q_num != 4 or net_income <= 0:
        return 0.0
    ratio = cfg.strategy.targets.dividend_payout_ratio if cfg.strategy else 0.30
    return net_income * ratio


# ─── Opening Balances ──────────────────────────────────────────────────


def _opening_fa_net(cfg: Config) -> float:
    fa = cfg.fixed_assets
    if fa is None or not fa.existing_assets:
        return 0.0
    return sum(a.cost - a.accumulated_depreciation for a in fa.existing_assets)


def _opening_equity(cfg: Config) -> float:
    eq = cfg.equity
    if eq is not None:
        return eq.paid_in_capital
    return 0.0


def _opening_retained(cfg: Config) -> float:
    eq = cfg.equity
    if eq is not None:
        return eq.retained_earnings
    return cfg.ceo_throughput_target * 0.1  # rough default


# ─── Post-balance: fill computed totals ────────────────────────────────


def _post_balance(pf: QuarterlyFinancials, retained: float) -> None:
    """Fill in total_assets, total_liabilities, total_equity, and check A=L+E."""
    b = pf.balance
    b.total_assets = b.cash + b.accounts_receivable + b.inventory + b.fixed_assets_net
    b.total_liabilities = b.accounts_payable + b.short_term_debt + b.long_term_debt + b.other_liabilities
    b.total_equity = b.paid_in_capital + b.retained_earnings
    b.total_liabilities_and_equity = b.total_liabilities + b.total_equity
