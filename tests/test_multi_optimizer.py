"""Tests for multi-dimensional business optimizer."""
from __future__ import annotations
import pytest
from copy import deepcopy
from datetime import date

from yusra_model.config.loader import Config
from yusra_model.models.multi_optimizer import (
    run_optimizer,
    compute_kpis,
    apply_params,
    check_constraints,
    MultiOptimizerResult,
    DEFAULT_GRID,
    DEFAULT_CONSTRAINTS,
    DEFAULT_WEIGHTS,
)
from yusra_model.engine.project import project_full
from yusra_model.domain import (
    StrategicContext, BusinessTargets,
    RevenueDrivers, ProductLine, SeasonalityProfile,
    CostStructure, OperatingExpenses, OpExCategory,
    WorkingCapitalPolicy, ReceivablesPolicy, PayablesPolicy, InventoryPolicy,
    EquityPosition, FixedAssets, CapExPlan, DepreciableAsset,
    TaxSettings,
)


def _make_cfg(**overrides) -> Config:
    """Create a Config with full domain objects for testing."""
    base = Config(
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
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class TestComputeKPIs:
    def test_compute_from_projection(self):
        cfg = _make_cfg()
        proj = project_full(cfg)
        assert proj.all_balanced()
        kpis = compute_kpis(proj)
        assert "revenue_cagr" in kpis
        assert "roe" in kpis
        assert "min_dscr" in kpis
        assert "min_cash" in kpis
        assert "total_throughput" in kpis
        assert kpis["revenue_cagr"] >= -1.0
        assert kpis["roe"] != 0.0

    def test_total_throughput_is_positive(self):
        cfg = _make_cfg()
        proj = project_full(cfg)
        kpis = compute_kpis(proj)
        assert kpis["total_throughput"] > 0

    def test_min_dscr_is_reasonable(self):
        cfg = _make_cfg()
        proj = project_full(cfg)
        kpis = compute_kpis(proj)
        assert kpis["min_dscr"] > 0.5
        assert kpis["min_dscr"] < 99.0


class TestApplyParams:
    def test_growth_multiplier_applied(self):
        cfg = _make_cfg()
        orig_rates = [pl.growth_rate for pl in cfg.revenue.product_lines]
        modified = apply_params(cfg, {"growth_multiplier": 2.0})
        for i, pl in enumerate(modified.revenue.product_lines):
            assert pl.growth_rate == pytest.approx(orig_rates[i] * 2.0)

    def test_price_multiplier_applied(self):
        cfg = _make_cfg()
        orig_prices = [pl.avg_price for pl in cfg.revenue.product_lines]
        modified = apply_params(cfg, {"price_multiplier": 1.1})
        for i, pl in enumerate(modified.revenue.product_lines):
            assert pl.avg_price == pytest.approx(orig_prices[i] * 1.1)

    def test_wc_efficiency_applied(self):
        cfg = _make_cfg()
        orig_dso = cfg.working_capital_policy.receivables.dso_target
        modified = apply_params(cfg, {"wc_efficiency": 0.8})
        assert modified.working_capital_policy.receivables.dso_target == int(orig_dso * 0.8)

    def test_leverage_multiplier_applied(self):
        cfg = _make_cfg()
        modified = apply_params(cfg, {"leverage_multiplier": 1.5})
        assert modified.total_facility == cfg.total_facility * 1.5
        assert modified.loans[0]["etb_principal"] == pytest.approx(cfg.loans[0]["etb_principal"] * 1.5, rel=1e-3)

    def test_tenor_applied(self):
        cfg = _make_cfg()
        modified = apply_params(cfg, {"tenor_quarters": 6})
        assert modified.loan_tenor_quarters == 6

    def test_default_params_no_change(self):
        cfg = _make_cfg()
        modified = apply_params(cfg, {})
        assert modified.total_facility == cfg.total_facility
        assert modified.loan_tenor_quarters == cfg.loan_tenor_quarters

    def test_original_unchanged(self):
        cfg = _make_cfg()
        orig_growth = [pl.growth_rate for pl in cfg.revenue.product_lines]
        apply_params(cfg, {"growth_multiplier": 5.0})
        for i, pl in enumerate(cfg.revenue.product_lines):
            assert pl.growth_rate == orig_growth[i]

    def test_no_revenue_domain_does_not_crash(self):
        cfg = _make_cfg()
        cfg.revenue = None
        modified = apply_params(cfg, {"growth_multiplier": 2.0})
        assert modified.revenue is None

    def test_no_wc_policy_does_not_crash(self):
        cfg = _make_cfg()
        cfg.working_capital_policy = None
        modified = apply_params(cfg, {"wc_efficiency": 0.8})
        assert modified.working_capital_policy is None


class TestCheckConstraints:
    def test_passes_when_above_threshold(self):
        feasible, violations = check_constraints({"min_dscr": 2.0, "min_cash": 1_000_000}, {"min_dscr": 1.2, "min_cash": 0})
        assert feasible
        assert violations == []

    def test_fails_when_below_threshold(self):
        feasible, violations = check_constraints({"min_dscr": 0.8}, {"min_dscr": 1.2})
        assert not feasible
        assert len(violations) == 1

    def test_missing_kpi_is_ignored(self):
        feasible, violations = check_constraints({}, {"min_dscr": 1.2})
        assert feasible
        assert violations == []


class TestRunOptimizer:
    def test_returns_multi_optimizer_result(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg)
        assert isinstance(result, MultiOptimizerResult)

    def test_default_grid_produces_243_variants(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg)
        expected = 1
        for v in DEFAULT_GRID.values():
            expected *= len(v)
        assert len(result.variants) == expected

    def test_some_variants_are_feasible(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg)
        assert result.n_feasible > 0

    def test_ranked_returns_top_n(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg)
        top = result.ranked(n=5)
        assert len(top) <= 5
        for v in top:
            assert v.feasible

    def test_pareto_front_returns_subset(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg)
        front = result.pareto_front("roe", "revenue_cagr")
        assert len(front) > 0
        assert len(front) <= result.n_feasible

    def test_small_grid(self):
        cfg = _make_cfg()
        grid = {"growth_multiplier": [0.5, 1.0], "tenor_quarters": [4, 8]}
        result = run_optimizer(cfg, grid=grid)
        assert len(result.variants) == 4

    def test_empty_grid_one_variant(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg, grid={})
        assert len(result.variants) == 1
        assert result.variants[0].params == {}

    def test_progress_callback_invoked(self):
        cfg = _make_cfg()
        calls = []
        run_optimizer(cfg, grid={"tenor_quarters": [4, 6, 8]}, progress_callback=lambda i, t: calls.append((i, t)))
        assert len(calls) == 3

    def test_different_constraints_filter(self):
        cfg = _make_cfg()
        strict = {"min_dscr": 100.0}  # likely infeasible for all
        result = run_optimizer(cfg, grid={"tenor_quarters": [8]}, constraints=strict)
        assert result.n_feasible == 0

    def test_all_variants_balanced(self):
        cfg = _make_cfg()
        result = run_optimizer(cfg, grid={"tenor_quarters": [4, 8], "growth_multiplier": [0.5, 1.0, 1.5]})
        inviable = [v for v in result.variants if "balance_check_failed" in v.constraint_violations]
        assert len(inviable) == 0
