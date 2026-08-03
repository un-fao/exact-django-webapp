"""Regression repro for bead exact-django-webapp-q58.

Perennial biomass: a user-supplied ``agb_maximum_c_tier_2 == 0.0`` must be
honoured as an explicit cap (same numeric behaviour as the ``1e-10`` value
users were forced to type as a workaround), NOT discarded by a truthiness
check and replaced with the tier-1 default ``agb_maximum_c``.

Django-free: the math model only depends on stdlib/numpy/matplotlib/PIL, so
this runs as a plain script:

    python djangoexact/math_model/tests/repro_perennial_agb_max_zero.py
"""

import os
import sys

# Make ``math_model`` importable: its package root is the djangoexact dir,
# which is two levels up from djangoexact/math_model/tests/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes  # noqa: E402
from math_model.no_time_dependency_final.perennial_cropping import PerennialCropland  # noqa: E402

# Tier-1 default cap, deliberately large so the buggy fallback is unmistakably
# different from the ~0 emissions a real zero cap produces.
AGB_MAXIMUM_C_DEFAULT = 100.0


def total_biomass_co2(agb_maximum_c_tier_2):
    """Build a perennial module with growth and return total BIOMASS CO2."""
    module = PerennialCropland(
        # BaseModule
        implementation_time=4,
        capitalization_time=16,
        rate_type="linear",
        delay=0,
        # LandModule
        hectares_start=10.0,
        hectares_end=10.0,
        soc_start_default=1.0,
        soc_end_default=1.0,
        fmg_start_default=1.0,
        fmg_end_default=1.0,
        flu_start_default=1.0,
        flu_end_default=1.0,
        fi_start_default=1.0,
        fi_end_default=1.0,
        calculate_soc_som=False,
        calculate_biomass=True,
        ef_nitrous_som=0.01,
        # PerennialCropland
        nitrous_constant=265.0,
        methane_constant=28.0,
        residue_burnt=False,
        emission_factor_burning_nitrous_residue=0.07,
        emission_factor_burning_methane=2.7,
        combustion_factor=0.5,
        fire_periodicity_default=1.0,
        agb_rate_default=2.0,
        agb_maximum_c=AGB_MAXIMUM_C_DEFAULT,
        bgb_rate_default=0.5,
        end_module_has_growth=True,
        agb_start_default=0.0,
        agb_maximum_c_tier_2=agb_maximum_c_tier_2,
    )
    module.calculate_emissions()

    total = 0.0
    for eset in module.result.yearly_emissions_by_sector_by_gas:
        if getattr(eset, "activity", None) == ActivityTypes.BIOMASS:
            total += sum(e.value for e in eset.emissions)
    return total


def main():
    zero = total_biomass_co2(0.0)
    epsilon = total_biomass_co2(0.0000000001)
    not_provided = total_biomass_co2(None)

    print(f"agb_maximum_c_tier_2 = 0.0          -> biomass CO2 = {zero:.6f}")
    print(f"agb_maximum_c_tier_2 = 1e-10        -> biomass CO2 = {epsilon:.6f}")
    print(f"agb_maximum_c_tier_2 = None (default)-> biomass CO2 = {not_provided:.6f}")

    failures = []

    # Core regression: an explicit 0.0 must behave like the 1e-10 workaround.
    if abs(zero - epsilon) > 1e-3:
        failures.append(
            f"0.0 ({zero:.6f}) != 1e-10 ({epsilon:.6f}): a real zero cap is "
            f"being discarded by a truthiness check."
        )

    # 0.0 must NOT silently fall back to the tier-1 default behaviour.
    if abs(zero - not_provided) < 1e-3:
        failures.append(
            f"0.0 ({zero:.6f}) == None/default ({not_provided:.6f}): an "
            f"explicit zero cap was replaced by the tier-1 default."
        )

    # "Not provided" must keep using the tier-1 default (behaviour preserved).
    if abs(not_provided) < 1e-3:
        failures.append(
            f"None should keep using the tier-1 default cap "
            f"({AGB_MAXIMUM_C_DEFAULT}); got near-zero {not_provided:.6f}."
        )

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nPASS: explicit 0.0 cap honoured; None still uses tier-1 default.")


if __name__ == "__main__":
    main()
