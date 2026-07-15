"""Taxation settings — corporate tax, VAT, withholding, loss carryforwards."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TaxSettings:
    corporate_income_tax_rate: float = 0.30
    vat_rate: float = 0.15
    withholding_tax_rate: float = 0.05
    tax_loss_carryforward_years: int = 5
    tax_installment_frequency_months: int = 3  # quarterly advance payments
