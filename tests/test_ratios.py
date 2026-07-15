"""Tests for financial ratios and KPI calculations"""
from __future__ import annotations
from yusra_model.models.ratios import calculate_ratios, FinancialRatios


class TestRatios:
    def test_calculate_ratios_returns_financialratios(self):
        r = calculate_ratios(
            opening_cash=10000000,
            opening_inventory=20000000,
            total_facility=70000000,
            gross_profit_margin=0.30,
            quarterly_sales=15000000,
            quarterly_repayments=3000000,
            quarterly_overheads=4000000,
            sales_cycle="3 Months",
        )
        assert isinstance(r, FinancialRatios)
        assert r.dscr != "N/A"

    def test_dscr_formula(self):
        r = calculate_ratios(
            opening_cash=10000000, opening_inventory=20000000,
            total_facility=70000000, gross_profit_margin=0.30,
            quarterly_sales=15000000, quarterly_repayments=3000000,
            quarterly_overheads=4000000, sales_cycle="3 Months",
        )
        expected_dscr = round((15000000 - 4000000) / 3000000, 2)
        assert r.dscr == expected_dscr

    def test_dscr_na_when_no_debt_service(self):
        r = calculate_ratios(
            opening_cash=10000000, opening_inventory=20000000,
            total_facility=70000000, gross_profit_margin=0.30,
            quarterly_sales=15000000, quarterly_repayments=0,
            quarterly_overheads=4000000, sales_cycle="3 Months",
        )
        assert r.dscr == "N/A"

    def test_inventory_turnover_3m(self):
        r = calculate_ratios(
            opening_cash=0, opening_inventory=0,
            total_facility=0, gross_profit_margin=0,
            quarterly_sales=0, quarterly_repayments=0,
            quarterly_overheads=0, sales_cycle="3 Months",
        )
        assert r.inventory_turnover == 4.0

    def test_inventory_turnover_6m(self):
        r = calculate_ratios(
            opening_cash=0, opening_inventory=0,
            total_facility=0, gross_profit_margin=0,
            quarterly_sales=0, quarterly_repayments=0,
            quarterly_overheads=0, sales_cycle="6 Months",
        )
        assert r.inventory_turnover == 2.0

    def test_current_ratio_non_zero(self):
        r = calculate_ratios(
            opening_cash=10000000, opening_inventory=20000000,
            total_facility=70000000, gross_profit_margin=0.30,
            quarterly_sales=15000000, quarterly_repayments=3000000,
            quarterly_overheads=4000000, sales_cycle="3 Months",
        )
        assert r.current_ratio > 0

    def test_cash_conversion_cycle_is_number(self):
        r = calculate_ratios(
            opening_cash=10000000, opening_inventory=20000000,
            total_facility=70000000, gross_profit_margin=0.30,
            quarterly_sales=15000000, quarterly_repayments=3000000,
            quarterly_overheads=4000000, sales_cycle="3 Months",
        )
        assert isinstance(r.cash_conversion_cycle, float)
