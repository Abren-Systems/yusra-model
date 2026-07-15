"""Tests for constraint-based throughput optimiser."""
from __future__ import annotations
from yusra_model.models.optimizer import optimize, _simulate_tenor, _max_throughput_simple, _compute_breakeven
from yusra_model.config.loader import Config
from datetime import date


def _make_cfg(
    facility: float = 70_000_000,
    ceo_target: float = 240_000_000,
    profit_rate: float = 0.07,
    overheads: float = 1_444_225.35,
    opening_cash: float = 16_927_876.79,
    opening_inv: float = 42_000_000,
) -> Config:
    return Config(
        company="Test Co",
        currency="ETB",
        opening_cash=opening_cash,
        opening_inventory=opening_inv,
        total_facility=facility,
        overheads_per_month=overheads,
        profit_rate=profit_rate,
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
            start_date=date(2026, 4, 7),
            quarterly_repayment=3_360_178,
            tenor_quarters=8,
            description="Test",
        )],
        ceo_throughput_target=ceo_target,
        plan_throughput_target=140_000_000,
        min_sales_buffer=500_000,
    )


class TestOptimizer:
    def test_optimise_returns_result(self):
        cfg = _make_cfg()
        result = optimize(cfg)
        assert result.optimum.max_throughput > 0
        assert result.optimum.max_multiplier >= 1.0

    def test_optimum_has_optimal_tenor(self):
        cfg = _make_cfg()
        result = optimize(cfg)
        assert 2 <= result.optimum.optimal_tenor <= 8

    def test_breakeven_positive(self):
        cfg = _make_cfg()
        result = optimize(cfg)
        assert result.breakeven_throughput > 0

    def test_gap_to_aspirational_non_negative(self):
        cfg = _make_cfg()
        result = optimize(cfg)
        assert result.gap_to_aspirational >= 0

    def test_solutions_contains_all_tenors(self):
        cfg = _make_cfg()
        result = optimize(cfg)
        assert len(result.solutions) == 7  # 2..8 inclusive

    def test_shorter_tenor_gives_higher_throughput(self):
        """Short tenors should allow more cycles = higher throughput."""
        sol_short = _simulate_tenor(2, 70_000_000, 0.07, 16_927_876.79, 42_000_000, 1_444_225.35 * 3, 0.30, 0)
        sol_long = _simulate_tenor(8, 70_000_000, 0.07, 16_927_876.79, 42_000_000, 1_444_225.35 * 3, 0.30, 0)
        assert sol_short.throughput >= sol_long.throughput

    def test_breakeven_covers_overheads_and_profit(self):
        result = _compute_breakeven(70_000_000, 0.07, 1_444_225.35 * 3, 0.30, 42_000_000)
        assert result > 70_000_000  # must be > facility

    def test_max_throughput_simple_returns_at_least_facility(self):
        for t in range(2, 9):
            val = _max_throughput_simple(70_000_000, 0.07, t)
            assert val >= 70_000_000

    def test_optimise_result_has_facility(self):
        cfg = _make_cfg(facility=100_000_000)
        result = optimize(cfg)
        assert result.facility == 100_000_000
