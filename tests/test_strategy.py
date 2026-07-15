"""Tests for the strategy & planning module."""
from __future__ import annotations
import pytest
from datetime import date

from yusra_model.config.loader import Config
from yusra_model.strategy.scenario import (
    ScenarioModifier, SCENARIOS, apply_modifier, run_scenarios, ScenarioResult,
)
from yusra_model.strategy.dashboard import build_comparison, print_comparison
from yusra_model.strategy.sensitivity import run_sensitivity, SensitivityResult
from yusra_model.domain import (
    StrategicContext, BusinessTargets,
    RevenueDrivers, ProductLine, SeasonalityProfile,
    CostStructure, OperatingExpenses, OpExCategory,
    WorkingCapitalPolicy, ReceivablesPolicy, PayablesPolicy, InventoryPolicy,
    EquityPosition, FixedAssets, CapExPlan, DepreciableAsset,
    TaxSettings,
)


def _make_cfg() -> Config:
    return Config(
        company="Test Pharma",
        currency="ETB",
        opening_cash=16_927_876.79,
        opening_inventory=42_000_000,
        total_facility=70_000_000,
        overheads_per_month=1_444_225.35,
        profit_rate=0.07,
        loan_tenor_quarters=8,
        baseline_rate=160.0,
        stress_rate=175.0,
        sales_cycle_options=["3 Months", "6 Months"],
        cash_ratio=0.85,
        credit_ratio=0.15,
        gross_profit_margin=0.30,
        loans=[dict(
            supplier="Test Supplier",
            usd_value=147354,
            etb_principal=23_580_195.28,
            effective_rate=160.0,
            start_date=date(2026, 4, 7),
            quarterly_repayment=3_360_178,
            tenor_quarters=8,
        )],
        ceo_throughput_target=240_000_000,
        plan_throughput_target=140_000_000,
        min_sales_buffer=500_000,
        strategy=StrategicContext(
            base_year=2026,
            planning_horizon_years=5,
            targets=BusinessTargets(dividend_payout_ratio=0.30),
        ),
        revenue=RevenueDrivers(
            product_lines=[
                ProductLine(name="Tab_Al", base_volume=250000, avg_price=850.0,
                            growth_rate=0.10, cogs_per_unit=595.0),
                ProductLine(name="Tab_Dol", base_volume=50000, avg_price=2500.0,
                            growth_rate=0.05, cogs_per_unit=1750.0),
                ProductLine(name="Cap_Am", base_volume=30000, avg_price=3500.0,
                            growth_rate=0.08, cogs_per_unit=2450.0),
            ],
            seasonality=SeasonalityProfile(q1=0.22, q2=0.26, q3=0.28, q4=0.24),
        ),
        costs=CostStructure(
            operating_expenses=OperatingExpenses(
                sales_marketing=OpExCategory(fixed_per_month=200000, variable_pct_of_revenue=0.02),
                distribution=OpExCategory(fixed_per_month=150000, variable_pct_of_revenue=0.01),
                admin=OpExCategory(fixed_per_month=300000, variable_pct_of_revenue=0.005),
                r_and_d=OpExCategory(fixed_per_month=100000, variable_pct_of_revenue=0.01),
                other=OpExCategory(fixed_per_month=50000, variable_pct_of_revenue=0.005),
            ),
            escalation_rate=0.08,
        ),
        working_capital_policy=WorkingCapitalPolicy(
            receivables=ReceivablesPolicy(dso_target=30),
            payables=PayablesPolicy(dpo_target=45),
            inventory=InventoryPolicy(finished_goods_days=60),
        ),
        equity=EquityPosition(paid_in_capital=10_000_000, retained_earnings=5_000_000),
        fixed_assets=FixedAssets(
            existing_assets=[
                DepreciableAsset(cost=15_000_000, accumulated_depreciation=3_000_000, useful_life_years=10),
            ],
            capex_plan=CapExPlan(year_1=2_000_000, year_2=1_500_000),
        ),
        taxation=TaxSettings(corporate_income_tax_rate=0.30),
    )


class TestScenarioModifier:
    def test_base_modifier_unchanged(self):
        cfg = _make_cfg()
        mod = SCENARIOS["base"]
        assert mod.growth_multiplier == 1.0
        modified = apply_modifier(cfg, mod)
        assert modified.total_facility == cfg.total_facility

    def test_upside_modifier_increases_growth(self):
        cfg = _make_cfg()
        orig_rates = [pl.growth_rate for pl in cfg.revenue.product_lines]
        modified = apply_modifier(cfg, SCENARIOS["upside"])
        for i, pl in enumerate(modified.revenue.product_lines):
            assert pl.growth_rate == pytest.approx(orig_rates[i] * 1.30)

    def test_stress_modifier_decreases_everything(self):
        cfg = _make_cfg()
        modified = apply_modifier(cfg, SCENARIOS["stress"])
        for pl in modified.revenue.product_lines:
            assert pl.growth_rate < 0.07
        assert modified.working_capital_policy.receivables.dso_target > 35

    def test_apply_modifier_preserves_original(self):
        cfg = _make_cfg()
        orig_facility = cfg.total_facility
        apply_modifier(cfg, SCENARIOS["stress"])
        assert cfg.total_facility == orig_facility


class TestRunScenarios:
    def test_base_scenario_runs(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base"])
        assert len(results) == 1
        assert results[0].balanced

    def test_all_scenarios_run(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base", "upside", "downside", "stress"])
        assert len(results) == 4
        for r in results:
            assert r.balanced, f"{r.name} not balanced"

    def test_upside_has_higher_growth_than_base(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base", "upside"])
        base_cagr = results[0].kpis.get("revenue_cagr", 0)
        upside_cagr = results[1].kpis.get("revenue_cagr", 0)
        assert upside_cagr >= base_cagr

    def test_stress_has_lower_kpis(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base", "stress"])
        base_ni = results[0].kpis.get("last_year_net_income", 0)
        stress_ni = results[1].kpis.get("last_year_net_income", 0)
        assert stress_ni <= base_ni

    def test_unknown_scenario_skipped(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base", "nonexistent"])
        assert len(results) == 1


class TestSensitivity:
    def test_returns_sensitivity_result(self):
        cfg = _make_cfg()
        result = run_sensitivity(cfg)
        assert isinstance(result, SensitivityResult)
        assert len(result.points) > 0

    def test_base_kpis_populated(self):
        cfg = _make_cfg()
        result = run_sensitivity(cfg)
        assert result.base_kpis.get("roe") is not None
        assert result.base_kpis.get("min_dscr") is not None

    def test_each_driver_has_four_points(self):
        cfg = _make_cfg()
        result = run_sensitivity(cfg)
        for driver in ["growth", "price", "wc", "leverage"]:
            points = result.for_driver(driver)
            assert len(points) == 4, f"{driver} has {len(points)} points"

    def test_higher_growth_increases_roe(self):
        cfg = _make_cfg()
        result = run_sensitivity(cfg)
        growth_points = result.for_driver("growth")
        pos = [p for p in growth_points if p.change_pct > 0]
        neg = [p for p in growth_points if p.change_pct < 0]
        if pos and neg:
            avg_pos_delta = sum(p.delta_kpis.get("roe", 0) for p in pos) / len(pos)
            avg_neg_delta = sum(p.delta_kpis.get("roe", 0) for p in neg) / len(neg)
            assert avg_pos_delta >= avg_neg_delta


class TestDashboard:
    def test_build_comparison_returns_headers_and_rows(self):
        cfg = _make_cfg()
        results = run_scenarios(cfg, ["base", "upside"])
        headers, rows = build_comparison(results)
        assert len(headers) == 3  # KPI + base + upside
        assert len(rows) > 0
        assert "KPI" in rows[0]
