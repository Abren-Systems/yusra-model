"""Financial statement dataclasses — one quarter, all three statements."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IncomeStatement:
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    opex_sales_marketing: float = 0.0
    opex_distribution: float = 0.0
    opex_admin: float = 0.0
    opex_r_and_d: float = 0.0
    opex_other: float = 0.0
    total_opex: float = 0.0
    ebitda: float = 0.0
    depreciation: float = 0.0
    ebit: float = 0.0
    interest_expense: float = 0.0
    ebt: float = 0.0
    tax_expense: float = 0.0
    net_income: float = 0.0


@dataclass
class BalanceSheet:
    cash: float = 0.0
    accounts_receivable: float = 0.0
    inventory: float = 0.0
    other_current_assets: float = 0.0
    fixed_assets_net: float = 0.0
    total_assets: float = 0.0
    accounts_payable: float = 0.0
    short_term_debt: float = 0.0
    long_term_debt: float = 0.0
    other_current_liabilities: float = 0.0
    other_liabilities: float = 0.0  # balancing item for opening gap
    total_liabilities: float = 0.0
    paid_in_capital: float = 0.0
    retained_earnings: float = 0.0
    total_equity: float = 0.0
    total_liabilities_and_equity: float = 0.0


@dataclass
class CashFlowStatement:
    net_income: float = 0.0
    depreciation: float = 0.0
    change_in_ar: float = 0.0
    change_in_inventory: float = 0.0
    change_in_ap: float = 0.0
    operating_cash_flow: float = 0.0
    capex: float = 0.0
    investing_cash_flow: float = 0.0
    drawdowns: float = 0.0
    repayments: float = 0.0
    dividends: float = 0.0
    financing_cash_flow: float = 0.0
    net_change_in_cash: float = 0.0
    opening_cash: float = 0.0
    closing_cash: float = 0.0


@dataclass
class QuarterlyFinancials:
    """One quarter's worth of all three statements + metadata."""
    period_label: str  # e.g. "Q1 2026"
    year: int = 0
    quarter: int = 0  # 1-4
    is_forecast: bool = True

    income: IncomeStatement = field(default_factory=IncomeStatement)
    balance: BalanceSheet = field(default_factory=BalanceSheet)
    cash_flow: CashFlowStatement = field(default_factory=CashFlowStatement)

    def balance_check(self) -> tuple[bool, float]:
        """Assets must equal Liabilities + Equity."""
        diff = abs(self.balance.total_assets - self.balance.total_liabilities_and_equity)
        return diff < 1.0, diff


@dataclass
class FinancialProjection:
    """Full multi-year projection result."""
    periods: list[QuarterlyFinancials] = field(default_factory=list)
    company: str = ""
    currency: str = ""
    base_year: int = 2025
    horizon_years: int = 5

    @property
    def n_quarters(self) -> int:
        return len(self.periods)

    def balance_checks(self) -> list[tuple[str, bool, float]]:
        return [(p.period_label,) + p.balance_check() for p in self.periods]

    def all_balanced(self) -> bool:
        return all(p.balance_check()[0] for p in self.periods)

    def income_table(self) -> list[dict]:
        return [
            {
                "period": p.period_label,
                "revenue": round(p.income.revenue, 0),
                "cogs": round(p.income.cogs, 0),
                "gross_profit": round(p.income.gross_profit, 0),
                "total_opex": round(p.income.total_opex, 0),
                "ebitda": round(p.income.ebitda, 0),
                "depreciation": round(p.income.depreciation, 0),
                "ebit": round(p.income.ebit, 0),
                "interest": round(p.income.interest_expense, 0),
                "ebt": round(p.income.ebt, 0),
                "tax": round(p.income.tax_expense, 0),
                "net_income": round(p.income.net_income, 0),
            }
            for p in self.periods
        ]

    def balance_table(self) -> list[dict]:
        return [
            {
                "period": p.period_label,
                "cash": round(p.balance.cash, 0),
                "ar": round(p.balance.accounts_receivable, 0),
                "inventory": round(p.balance.inventory, 0),
                "fa_net": round(p.balance.fixed_assets_net, 0),
                "total_assets": round(p.balance.total_assets, 0),
                "ap": round(p.balance.accounts_payable, 0),
                "debt": round(p.balance.short_term_debt + p.balance.long_term_debt, 0),
                "total_liabilities": round(p.balance.total_liabilities, 0),
                "equity": round(p.balance.total_equity, 0),
            }
            for p in self.periods
        ]

    def cash_flow_table(self) -> list[dict]:
        return [
            {
                "period": p.period_label,
                "ocf": round(p.cash_flow.operating_cash_flow, 0),
                "icf": round(p.cash_flow.investing_cash_flow, 0),
                "fcf": round(p.cash_flow.financing_cash_flow, 0),
                "net_change": round(p.cash_flow.net_change_in_cash, 0),
                "opening_cash": round(p.cash_flow.opening_cash, 0),
                "closing_cash": round(p.cash_flow.closing_cash, 0),
            }
            for p in self.periods
        ]
