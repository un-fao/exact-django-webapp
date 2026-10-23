"""Manure nitrogen beyond excretion, IPCC 2019 Refinement Vol. 4 Ch. 10.

Co-digestate N (N_cdg, kg N/yr) joins the anaerobic digester flow in Eq. 10.25 (direct, EF3), 10.26 (FracGasMS) and
10.27 (FracLeachMS). Bedding N (N_beddingMS, kg N/animal/yr) appears only in Eq. 10.34: section 10.5.4 assumes no
volatilisation or leaching from bedding and Eq. 10.25 has no bedding term, so bedding adds no N2O.
"""

from typing import Optional, Sequence

DIGESTER = "Digester"
BEDDING_SYSTEMS = ("Solid Storage", "Deep Bedding")
# Table 10.23 default R_N2(N2O), kg N2-N per kg N2O-N (Eq. 10.34b).
R_N2_N2O = 3


def effective_system_shares(percentage_system_default: Sequence[float], percentage_prp_default: float, percentage_prp_tier_2: Optional[float] = None) -> list[float]:
    """Fractions of excreted N per managed system, rescaled for a tier 2 PRP share the way gas_head_calculation does."""
    shares = [100 - percentage_prp_default] if len(percentage_system_default) == 1 else list(percentage_system_default)
    if percentage_prp_tier_2 is not None:
        if percentage_prp_default >= 100:
            return [0.0] * len(shares)
        shares = [s * (100 - percentage_prp_tier_2) / (100 - percentage_prp_default) for s in shares]
    return [s / 100 for s in shares]


def share_of(names: Sequence[Optional[str]], shares: Sequence[float], systems: Sequence[str]) -> float:
    return sum(share for name, share in zip(names, shares) if name in systems)


def frac_loss(ef3: float, frac_gas: float, frac_leach: float) -> float:
    """Eq. 10.34a with FracN2MS = R_N2(N2O) x EF3 (Eq. 10.34b)."""
    return frac_gas + frac_leach + ef3 * (1 + R_N2_N2O)


def codigestate_n2o_n(n_cdg: float, ef3: float, frac_gas: float, frac_leach: float, ef4: float, ef5: float) -> tuple[float, float, float]:
    """kg N2O-N/yr from co-digestate: direct (Eq. 10.25), volatilisation (Eq. 10.26 x EF4), leaching (Eq. 10.27 x EF5)."""
    return n_cdg * ef3, n_cdg * frac_gas * ef4, n_cdg * frac_leach * ef5


def managed_manure_n_available(
    heads: float,
    nex: float,
    names: Sequence[Optional[str]],
    shares: Sequence[float],
    ef3: Sequence[float],
    frac_gas: Sequence[float],
    frac_leach: Sequence[float],
    n_cdg: float = 0.0,
    n_bedding: float = 0.0,
) -> float:
    """Eq. 10.34, kg N/yr left after management losses, for soils, feed, fuel or construction.

    nex is kg N/animal/yr; names, shares (fractions) and the loss factors are aligned per managed system (PRP excluded).
    """
    total = 0.0
    for name, share, e3, gas, leach in zip(names, shares, ef3, frac_gas, frac_leach):
        n_managed = heads * nex * share + (n_cdg if name == DIGESTER else 0.0)
        total += n_managed * (1 - frac_loss(e3, gas, leach))
        if name in BEDDING_SYSTEMS:
            total += heads * share * n_bedding
    return total
