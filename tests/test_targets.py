"""Tests for recycling targets and velocity scenarios — driven by optimizer."""
from __future__ import annotations
from yusra_model.models.targets import (
    build_targets, build_velocity_scenarios, compute_path_to_240m,
)
from yusra_model.config.loader import Config
from datetime import date


def _make_cfg(
    ceo_target: float = 240_000_000,
    facility: float = 70_000_000,
    profit_rate: float = 0.07,
) -> Config:
    return Config(
        company="Test Co",
        currency="ETB",
        opening_cash=16_927_876.79,
        opening_inventory=42_000_000,
        total_facility=facility,
        overheads_per_month=1_444_225.35,
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


class TestTargets:
    def test_build_targets_contains_breakeven(self):
        cfg = _make_cfg()
        targets = build_targets(cfg)
        labels = [t.label for t in targets]
        assert any("Breakeven" in l for l in labels)

    def test_target_multiplier_increases(self):
        cfg = _make_cfg()
        targets = build_targets(cfg)
        multipliers = [t.multiplier for t in targets]
        assert multipliers == sorted(multipliers)

    def test_aspirational_target_included_when_different(self):
        cfg = _make_cfg(ceo_target=240_000_000)
        targets = build_targets(cfg)
        assert any("Aspirational" in t.label for t in targets)

    def test_velocity_scenarios_contains_feasible(self):
        cfg = _make_cfg()
        scenarios = build_velocity_scenarios(cfg)
        assert any("Feasible" in s.feasibility for s in scenarios)

    def test_velocity_scenarios_contains_aspirational(self):
        cfg = _make_cfg()
        scenarios = build_velocity_scenarios(cfg)
        assert any("Aspirational" in s.scenario for s in scenarios)

    def test_compute_path_to_240m_returns_steps(self):
        cfg = _make_cfg()
        steps = compute_path_to_240m(base_throughput=70_000_000, facility=70_000_000)
        assert len(steps) >= 2
        assert all("step" in s for s in steps)

    def test_path_cumulative_increases(self):
        cfg = _make_cfg()
        steps = compute_path_to_240m(base_throughput=70_000_000, facility=70_000_000)
        cumuls = [s["cumulative"] for s in steps]
        assert cumuls == sorted(cumuls)
