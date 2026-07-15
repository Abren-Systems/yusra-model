"""Tests for config validation business rules"""
from __future__ import annotations
from datetime import date
from yusra_model.config.validation import validate_business_rules
from yusra_model.config.loader import Config


def _make_cfg(
    cash_ratio=0.85,
    credit_ratio=0.15,
    opening_cash=10000000,
    opening_inventory=20000000,
    total_facility=70000000,
    overheads_per_month=1444225.35,
    gross_profit_margin=0.30,
    profit_rate=0.07,
    baseline_rate=160,
    stress_rate=175,
    loans=None,
):
    if loans is None:
        loans = [{"supplier": "A", "usd_value": 100000, "effective_rate": 160,
                  "start_date": date(2026, 4, 1), "etb_principal": 10000000,
                  "quarterly_repayment": 1500000}]
    return Config(
        company="Test", currency="ETB",
        opening_cash=opening_cash, opening_inventory=opening_inventory,
        total_facility=total_facility, overheads_per_month=overheads_per_month,
        profit_rate=profit_rate, loan_tenor_quarters=8,
        baseline_rate=baseline_rate, stress_rate=stress_rate,
        sales_cycle_options=["3 Months", "6 Months"],
        cash_ratio=cash_ratio, credit_ratio=credit_ratio,
        gross_profit_margin=gross_profit_margin,
        loans=loans,
        ceo_throughput_target=240000000, plan_throughput_target=140000000,
        min_sales_buffer=500000,
    )


class TestValidation:
    def test_valid_config_no_warnings(self):
        loans = [{"supplier": "A", "usd_value": 100000, "effective_rate": 160,
                  "start_date": date(2026, 4, 1), "etb_principal": 40000000,
                  "quarterly_repayment": 6000000}]
        cfg = _make_cfg(loans=loans)
        warnings = validate_business_rules(cfg)
        assert warnings == []

    def test_ratio_warning(self):
        cfg = _make_cfg(cash_ratio=0.90, credit_ratio=0.05)
        warnings = validate_business_rules(cfg)
        assert any("cash_ratio" in w and "credit_ratio" in w for w in warnings)

    def test_negative_cash_warning(self):
        cfg = _make_cfg(opening_cash=-1000)
        warnings = validate_business_rules(cfg)
        assert any("opening_cash" in w and "negative" in w for w in warnings)

    def test_negative_inventory_warning(self):
        cfg = _make_cfg(opening_inventory=-1)
        warnings = validate_business_rules(cfg)
        assert any("opening_inventory" in w for w in warnings)

    def test_zero_facility_warning(self):
        cfg = _make_cfg(total_facility=0)
        warnings = validate_business_rules(cfg)
        assert any("total_facility" in w for w in warnings)

    def test_stress_rate_below_baseline_warning(self):
        cfg = _make_cfg(baseline_rate=160, stress_rate=150)
        warnings = validate_business_rules(cfg)
        assert any("stress_rate" in w for w in warnings)

    def test_profit_rate_out_of_range_warning(self):
        cfg = _make_cfg(profit_rate=0.0)
        warnings = validate_business_rules(cfg)
        assert any("profit_rate" in w for w in warnings)

    def test_principal_exceeds_facility_warning(self):
        loans = [{"supplier": "A", "usd_value": 1000000, "effective_rate": 160,
                  "start_date": date(2026, 4, 1), "etb_principal": 80000000,
                  "quarterly_repayment": 12000000}]
        cfg = _make_cfg(loans=loans, total_facility=70000000)
        warnings = validate_business_rules(cfg)
        print(f"\nDEBUG warnings: {warnings}")
        for w in warnings:
            print(f"  checking '{'explicit' in w.lower()}' in {w}")
        assert any("explicit" in w.lower() for w in warnings)

    def test_high_overheads_warning(self):
        cfg = _make_cfg(overheads_per_month=5000000, total_facility=10000000)
        warnings = validate_business_rules(cfg)
        assert any("overheads" in w.lower() for w in warnings)

    def test_no_warnings_for_missing_loans(self):
        cfg = _make_cfg(loans=[])
        warnings = validate_business_rules(cfg)
        assert isinstance(warnings, list)
