"""Shared test fixtures"""
from __future__ import annotations
from datetime import date
import pytest
from yusra_model.models.loans import Loan, Portfolio
from yusra_model.config.loader import Config


@pytest.fixture
def sample_loan():
    return Loan(
        supplier="Test Supplier",
        usd_value=100000,
        etb_principal=None,
        effective_rate=160.0,
        start_date=date(2026, 4, 1),
        quarterly_repayment=None,
        tenor_quarters=8,
        profit_rate=0.07,
    )


@pytest.fixture
def fully_defined_loan():
    return Loan(
        supplier="Fixed Supplier",
        usd_value=50000,
        etb_principal=8000000.0,
        effective_rate=160.0,
        start_date=date(2026, 4, 7),
        quarterly_repayment=1150000.0,
        tenor_quarters=8,
        profit_rate=0.07,
    )


@pytest.fixture
def sample_portfolio():
    loans = [
        Loan("A", 100000, None, 160.0, date(2026, 4, 1), None),
        Loan("B", 50000, None, 160.0, date(2026, 10, 1), None),
    ]
    return Portfolio(tuple(loans), total_facility=70000000, profit_rate=0.07)


@pytest.fixture
def sample_config_dict():
    return {
        "company": "Test Pharma",
        "currency": "ETB",
        "parameters": {
            "opening_cash": 10000000,
            "opening_inventory": 20000000,
            "total_facility": 70000000,
            "overheads_per_month": 1444225.35,
            "profit_rate": 0.07,
            "loan_tenor_quarters": 8,
        },
        "exchanges": {"baseline": 160, "stress": 175},
        "sales": {
            "cycle_options": ["3 Months", "6 Months"],
            "cash_ratio": 0.85,
            "credit_ratio": 0.15,
            "gross_profit_margin": 0.30,
        },
        "loans": [
            {"supplier": "Supplier A", "usd_value": 147354, "etb_principal": 23580195.28,
             "effective_rate": 160.0, "start_date": "2026-04-07", "quarterly_repayment": 3360178},
        ],
        "targets": {
            "ceo_throughput": 240000000,
            "plan_throughput": 140000000,
            "min_sales_buffer": 500000,
        },
    }
