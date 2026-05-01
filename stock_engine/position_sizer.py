"""
Kelly Criterion + fixed-fractional position sizer.
Prevents ruin — the real edge in trading is survival.
"""

def kelly_size(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly fraction. Cap at 25% — full Kelly is reckless."""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    return round(max(0.0, min(kelly, 0.25)), 4)  # hard cap 25%


def size_position(
    capital: float,
    score: float,
    regime: str,
    stop_pct: float = 0.05,
    win_rate: float = 0.55,
    avg_win: float = 0.08,
    avg_loss: float = 0.04,
) -> dict:
    """
    capital   — total account size
    score     — screener score 0-100
    regime    — BULL / BEAR / CHOP
    stop_pct  — where you'll cut the loss (default 5%)
    """
    kelly = kelly_size(win_rate, avg_win, avg_loss)

    # Scale by signal conviction
    if score >= 80:   conviction = 1.0
    elif score >= 70: conviction = 0.75
    elif score >= 60: conviction = 0.5
    else:             conviction = 0.25

    # Scale by regime
    regime_mult = {"BULL": 1.0, "CHOP": 0.75, "BEAR": 0.5}.get(regime.split()[0], 0.75)

    raw_pct = kelly * conviction * regime_mult
    risk_dollars = capital * raw_pct

    # Shares: risk per share = stop_pct of entry price
    # We return as dollar amount — caller divides by (price * stop_pct)
    return {
        "risk_pct":      round(raw_pct * 100, 2),
        "risk_dollars":  round(risk_dollars, 2),
        "note": f"Kelly={kelly:.2%} | conviction={conviction:.0%} | regime_mult={regime_mult:.0%}",
    }


if __name__ == "__main__":
    capitals = [100, 1_000, 5_000, 10_000]
    print("\n  POSITION SIZING EXAMPLES  (score=75, BULL regime, 5% stop)\n")
    print(f"  {'Capital':>10}  {'Risk%':>7}  {'Risk$':>8}  {'Note'}")
    print(f"  {'-'*60}")
    for cap in capitals:
        r = size_position(cap, score=75, regime="BULL")
        print(f"  ${cap:>9,}  {r['risk_pct']:>6.2f}%  ${r['risk_dollars']:>7.2f}  {r['note']}")
    print()
