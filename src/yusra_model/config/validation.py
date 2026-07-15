"""Business-rule validation for configuration inputs"""
from __future__ import annotations
from .loader import Config


def validate_business_rules(cfg: Config) -> list[str]:
    """Check config for suspicious or inconsistent values. Returns warning messages."""
    warnings: list[str] = []

    # Ratio consistency
    ratio_sum = cfg.cash_ratio + cfg.credit_ratio
    if abs(ratio_sum - 1.0) > 0.01:
        warnings.append(
            f"cash_ratio ({cfg.cash_ratio}) + credit_ratio ({cfg.credit_ratio}) "
            f"= {ratio_sum}, expected ~1.0"
        )

    # Non-negative checks
    if cfg.opening_cash < 0:
        warnings.append(f"opening_cash is negative ({cfg.opening_cash})")
    if cfg.opening_inventory < 0:
        warnings.append(f"opening_inventory is negative ({cfg.opening_inventory})")
    if cfg.total_facility <= 0:
        warnings.append(f"total_facility must be positive ({cfg.total_facility})")
    if cfg.overheads_per_month <= 0:
        warnings.append(f"overheads_per_month should be positive ({cfg.overheads_per_month})")
    if cfg.gross_profit_margin <= 0:
        warnings.append(f"gross_profit_margin should be positive ({cfg.gross_profit_margin})")

    # Rate sanity
    if cfg.profit_rate <= 0 or cfg.profit_rate >= 1:
        warnings.append(f"profit_rate ({cfg.profit_rate}) outside expected range (0, 1)")
    if cfg.baseline_rate <= 0:
        warnings.append(f"baseline exchange rate must be positive ({cfg.baseline_rate})")
    if cfg.stress_rate < cfg.baseline_rate:
        warnings.append(
            f"stress_rate ({cfg.stress_rate}) is lower than baseline_rate ({cfg.baseline_rate})"
        )

    # Loan checks
    if cfg.loans:
        total_loan_usd = sum(l.get("usd_value", 0) for l in cfg.loans)
        total_loan_etb = sum(l.get("etb_principal") or 0 for l in cfg.loans)
        if total_loan_etb > cfg.total_facility:
            warnings.append(
                f"Total explicit ETB principal ({total_loan_etb:,.0f}) exceeds "
                f"total facility ({cfg.total_facility:,.0f})"
            )
        if total_loan_etb > 0 and total_loan_etb < cfg.total_facility * 0.5:
            warnings.append(
                f"Explicit ETB principal ({total_loan_etb:,.0f}) is less than 50% of "
                f"facility ({cfg.total_facility:,.0f}) — most will be auto-allocated"
            )

        for loan in cfg.loans:
            supplier = loan.get("supplier", "?")
            if loan.get("usd_value", 0) <= 0:
                warnings.append(f"Loan '{supplier}' has non-positive usd_value")
            if loan.get("effective_rate", 0) <= 0:
                warnings.append(f"Loan '{supplier}' has non-positive effective_rate")

    # Overheads sanity
    annual_overheads = cfg.overheads_per_month * 12
    if annual_overheads > cfg.total_facility * 0.5:
        warnings.append(
            f"Annual overheads ({annual_overheads:,.0f}) exceed 50% of facility "
            f"({cfg.total_facility:,.0f}) — verify"
        )

    return warnings
