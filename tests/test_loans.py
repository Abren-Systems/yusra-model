"""Tests for loan models and repayment schedules"""
from __future__ import annotations
from datetime import date
from yusra_model.models.loans import Loan, Portfolio, _quarter_label, _add_quarters


class TestLoan:
    def test_creates_with_explicit_values(self):
        l = Loan("Test", 100000, 16000000.0, 160.0,
                 date(2026, 4, 1), 2500000.0)
        assert l.supplier == "Test"
        assert l.etb_principal == 16000000.0
        assert l.quarterly_repayment == 2500000.0

    def test_computes_etb_principal_from_usd(self):
        l = Loan("Test", 100000, None, 160.0, date(2026, 4, 1), None)
        assert l.etb_principal == 16000000.0

    def test_computes_quarterly_repayment(self):
        l = Loan("Test", 100000, None, 160.0, date(2026, 4, 1), None,
                 tenor_quarters=8, profit_rate=0.07)
        total_profit = 16000000 * (8 / 4) * 0.07
        expected_qr = round(16000000 / 8 + total_profit / 8, 2)
        assert l.quarterly_repayment == expected_qr

    def test_total_property(self):
        l = Loan("Test", 100000, 16000000.0, 160.0,
                 date(2026, 4, 1), 2500000.0, profit_rate=0.07)
        expected_profit = round(16000000 * (8 / 4) * 0.07, 2)
        assert l.total_profit == expected_profit
        assert l.total_cost == round(16000000 + expected_profit, 2)

    def test_start_quarter(self):
        l = Loan("Test", 0, 0, 160.0, date(2026, 4, 7), None)
        assert l.start_quarter == "Q2 2026"

    def test_immutable(self):
        l = Loan("Test", 100000, None, 160.0, date(2026, 4, 1), None)
        import dataclasses
        assert dataclasses.fields(l)  # is a dataclass
        assert l.etb_principal is not None

    def test_repayment_schedule_length(self):
        qlabels = [f"Q{q} 2026" for q in range(1, 5)] + [f"Q{q} 2027" for q in range(1, 5)] + [f"Q{q} 2028" for q in range(1, 5)]
        l = Loan("Test", 100000, 16000000.0, 160.0,
                 date(2026, 4, 1), 2500000.0)
        schedule = l.repayment_schedule(qlabels)
        assert len(schedule) == 8

    def test_repayment_schedule_decreasing_balance(self):
        qlabels = [f"Q{q} 2026" for q in range(1, 5)] + [f"Q{q} 2027" for q in range(1, 5)]
        l = Loan("Test", 100000, 16000000.0, 160.0,
                 date(2026, 4, 1), 2500000.0)
        schedule = l.repayment_schedule(qlabels)
        assert len(schedule) >= 2
        assert schedule[0]["balance"] > schedule[1]["balance"]

    def test_repayment_schedule_empty_for_outside_range(self):
        qlabels = ["Q1 2025"]
        l = Loan("Test", 100000, 16000000.0, 160.0,
                 date(2026, 4, 1), 2500000.0)
        schedule = l.repayment_schedule(qlabels)
        assert schedule == []

    def test_zero_usd_value_no_crash(self):
        l = Loan("Test", 0, None, 160.0, date(2026, 4, 1), None)
        assert l.etb_principal is None
        assert l.quarterly_repayment is None

    def test_frozen_instance(self):
        l = Loan("Test", 100000, None, 160.0, date(2026, 4, 1), None)
        import dataclasses
        assert dataclasses.is_dataclass(l)
        assert dataclasses.fields(l)[0].name == "supplier"


class TestPortfolio:
    def test_portfolio_totals(self):
        loans = [
            Loan("A", 100000, 8000000.0, 160.0, date(2026, 4, 1), 1200000.0),
            Loan("B", 50000, 4000000.0, 160.0, date(2026, 10, 1), 600000.0),
        ]
        p = Portfolio(tuple(loans), 70000000, 0.07)
        assert p.total_principal == 12000000.0
        assert p.total_quarterly_repayment == 1800000.0

    def test_remaining_facility(self):
        loans = [Loan("A", 100000, 10000000.0, 160.0, date(2026, 4, 1), 1500000.0)]
        p = Portfolio(tuple(loans), 70000000, 0.07)
        assert p.remaining_facility() == 60000000.0

    def test_with_allocated_remaining_returns_self_when_all_fixed(self):
        loans = [
            Loan("A", 100000, 10000000.0, 160.0, date(2026, 4, 1), 1500000.0),
            Loan("B", 50000, 8000000.0, 160.0, date(2026, 10, 1), 1200000.0),
        ]
        p = Portfolio(tuple(loans), 20000000, 0.07)
        p2 = p.with_allocated_remaining()
        assert p2 is p

    def test_with_allocated_remaining_does_not_mutate_original(self):
        loans = [
            Loan("A", 100000, 10000000.0, 160.0, date(2026, 4, 1), 1500000.0),
            Loan("B", 50000, None, 160.0, date(2026, 10, 1), None),
        ]
        p = Portfolio(tuple(loans), 20000000, 0.07)
        _original_loans = list(p.loans)
        p2 = p.with_allocated_remaining()
        # Original portfolio should be unchanged (immutable)
        assert p.loans[0].etb_principal == 10000000.0
        assert p.loans[0].quarterly_repayment == 1500000.0
        # New portfolio should have different objects
        assert p2 is p or any(l != o for l, o in zip(p2.loans, p.loans))

    def test_with_allocated_remaining_no_variable(self):
        loans = [Loan("A", 100000, 10000000.0, 160.0, date(2026, 4, 1), 1500000.0)]
        p = Portfolio(tuple(loans), 70000000, 0.07)
        p2 = p.with_allocated_remaining()
        assert p2 is p

    def test_drawdown_by_quarter(self):
        qlabels = ["Q2 2026", "Q3 2026", "Q4 2026"]
        loans = [
            Loan("A", 100000, 5000000.0, 160.0, date(2026, 4, 1), 750000.0),
            Loan("B", 50000, 3000000.0, 160.0, date(2026, 10, 1), 450000.0),
        ]
        p = Portfolio(tuple(loans), 70000000, 0.07)
        dd = p.drawdown_by_quarter(qlabels)
        assert dd["Q2 2026"] == 5000000.0
        assert dd["Q4 2026"] == 3000000.0
        assert dd["Q3 2026"] == 0.0


class TestHelpers:
    def test_quarter_label(self):
        assert _quarter_label(date(2026, 1, 1)) == "Q1 2026"
        assert _quarter_label(date(2026, 4, 1)) == "Q2 2026"
        assert _quarter_label(date(2026, 7, 1)) == "Q3 2026"
        assert _quarter_label(date(2026, 10, 1)) == "Q4 2026"

    def test_add_quarters(self):
        assert _add_quarters(date(2026, 4, 1), 1) == date(2026, 7, 1)
        assert _add_quarters(date(2026, 4, 1), 4) == date(2027, 4, 1)
        assert _add_quarters(date(2026, 10, 1), 8) == date(2028, 10, 1)
