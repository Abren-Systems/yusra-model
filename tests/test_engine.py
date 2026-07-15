"""Tests for the three-statement financial projection engine."""
from __future__ import annotations
from yusra_model.config.loader import load_config
from yusra_model.engine import project_full, FinancialProjection, QuarterlyFinancials
from yusra_model.engine.project import _horizon, _project_revenue, _project_opex
from yusra_model.domain import RevenueDrivers, ProductLine, SeasonalityProfile


SAMPLE_CFG = "config/default.yaml"


def _cfg():
    return load_config(SAMPLE_CFG)


class TestHorizon:
    def test_returns_20_quarters_for_5_years(self):
        h = _horizon(_cfg())
        assert len(h) == 20

    def test_starts_at_base_year(self):
        h = _horizon(_cfg())
        assert h[0] == (2025, 1)

    def test_ends_at_base_plus_horizon(self):
        cfg = _cfg()
        base = cfg.strategy.base_year
        yrs = cfg.strategy.planning_horizon_years
        h = _horizon(cfg)
        assert h[-1] == (base + yrs - 1, 4)


class TestRevenue:
    def test_product_line_revenue_positive(self):
        rev, cogs = _project_revenue(_cfg(), 2025, 1, 0)
        assert rev > 0
        assert cogs > 0

    def test_revenue_grows_over_time(self):
        rev1, _ = _project_revenue(_cfg(), 2025, 1, 0)
        rev5, _ = _project_revenue(_cfg(), 2029, 1, 4)
        assert rev5 > rev1

    def test_seasonality_affects_q4(self):
        rev_q1, _ = _project_revenue(_cfg(), 2025, 1, 0)
        rev_q4, _ = _project_revenue(_cfg(), 2025, 4, 0)
        assert rev_q4 > rev_q1  # default seasonality has Q4 highest (0.29)


class TestFullProjection:
    def test_returns_correct_number_of_periods(self):
        proj = project_full(_cfg())
        assert proj.n_quarters == 20

    def test_all_periods_balance(self):
        proj = project_full(_cfg())
        assert proj.all_balanced()

    def test_revenue_increases_each_year(self):
        proj = project_full(_cfg())
        ann = {}
        for p in proj.periods:
            ann[p.year] = ann.get(p.year, 0) + p.income.revenue
        revenues = [ann[y] for y in sorted(ann)]
        for i in range(1, len(revenues)):
            assert revenues[i] > revenues[i - 1]

    def test_net_income_positive(self):
        proj = project_full(_cfg())
        for p in proj.periods:
            assert p.income.net_income >= 0

    def test_has_company_name(self):
        proj = project_full(_cfg())
        assert proj.company == "YUSRA PHARMA PLC"

    def test_cash_never_negative(self):
        proj = project_full(_cfg())
        for p in proj.periods:
            assert p.balance.cash >= -1, f"Cash negative in {p.period_label}"

    def test_income_table_has_expected_keys(self):
        proj = project_full(_cfg())
        table = proj.income_table()
        assert len(table) == 20
        assert "revenue" in table[0]
        assert "net_income" in table[0]

    def test_balance_table_has_expected_keys(self):
        proj = project_full(_cfg())
        table = proj.balance_table()
        assert len(table) == 20
        assert "total_assets" in table[0]

    def test_cash_flow_table_has_expected_keys(self):
        proj = project_full(_cfg())
        table = proj.cash_flow_table()
        assert len(table) == 20
        assert "ocf" in table[0]

    def test_opening_closing_cash_consistent(self):
        proj = project_full(_cfg())
        for i in range(1, len(proj.periods)):
            prev = proj.periods[i - 1]
            curr = proj.periods[i]
            assert abs(curr.cash_flow.opening_cash - prev.cash_flow.closing_cash) < 1.0

    def test_gross_profit_positive(self):
        proj = project_full(_cfg())
        for p in proj.periods:
            assert p.income.gross_profit > 0

    def test_ebitda_positive(self):
        proj = project_full(_cfg())
        for p in proj.periods:
            assert p.income.ebitda > 0

    def test_equity_grows_with_retained_earnings(self):
        proj = project_full(_cfg())
        first_eq = proj.periods[0].balance.total_equity
        last_eq = proj.periods[-1].balance.total_equity
        assert last_eq > first_eq

    def test_debt_service_in_2026(self):
        """When legacy loans are drawn in 2026, debt outstanding should be >0."""
        proj = project_full(_cfg())
        q2_2026 = [p for p in proj.periods if p.period_label == "Q2 2026"]
        assert len(q2_2026) == 1
        assert q2_2026[0].cash_flow.drawdowns > 0
