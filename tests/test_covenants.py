"""Tests for covenant monitoring"""
from __future__ import annotations
from datetime import date
from yusra_model.models.loans import Loan, Portfolio
from yusra_model.models.cashflow import _project_single_cycle
from yusra_model.models.covenants import check_all, check_dscr, check_current_ratio
from yusra_model.config.loader import Config


def _make_test_portfolio():
    loans = [
        Loan("A", 100000, 5000000.0, 160.0, date(2026, 4, 1), 750000.0,
             tenor_quarters=8, profit_rate=0.07),
    ]
    return Portfolio(tuple(loans), total_facility=70000000, profit_rate=0.07)


def _make_test_cfg():
    return Config(
        company="Test", currency="ETB",
        opening_cash=10000000, opening_inventory=20000000,
        total_facility=70000000, overheads_per_month=1444225.35,
        profit_rate=0.07, loan_tenor_quarters=8,
        baseline_rate=160, stress_rate=175,
        sales_cycle_options=["3 Months", "6 Months"],
        cash_ratio=0.85, credit_ratio=0.15, gross_profit_margin=0.30,
        loans=[{"supplier": "A", "usd_value": 100000, "effective_rate": 160,
                "start_date": date(2026, 4, 1), "etb_principal": 5000000,
                "quarterly_repayment": 750000}],
        ceo_throughput_target=240000000, plan_throughput_target=140000000,
        min_sales_buffer=500000,
    )


class TestCovenants:
    def test_check_dscr_returns_covenant(self):
        p = _make_test_portfolio()
        proj = _project_single_cycle("test", p, 10000000, 20000000,
                                     4000000, 0.30, sell_fraction=1.0)
        result = check_dscr(p, proj)
        assert hasattr(result, "metric")
        assert result.metric == "DSCR (Q1)"

    def test_check_all_returns_list(self):
        p = _make_test_portfolio()
        proj = _project_single_cycle("test", p, 10000000, 20000000,
                                     4000000, 0.30, sell_fraction=1.0)
        cfg = _make_test_cfg()
        results = check_all(p, proj, cfg)
        assert isinstance(results, list)
        assert len(results) == 4

    def test_current_ratio_returns_covenant(self):
        p = _make_test_portfolio()
        proj = _project_single_cycle("test", p, 10000000, 20000000,
                                     4000000, 0.30, sell_fraction=1.0)
        result = check_current_ratio(p, proj)
        assert hasattr(result, "status")

    def test_covenant_status_is_string(self):
        p = _make_test_portfolio()
        proj = _project_single_cycle("test", p, 10000000, 20000000,
                                     4000000, 0.30, sell_fraction=1.0)
        result = check_dscr(p, proj)
        assert result.status in ("pass", "warning", "breach")
