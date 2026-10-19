"""Rewetting of inland wetland mineral soils (IWMS), IPCC 2013 Wetlands Supplement, chapter 5.

CH4 follows Equation 5.1 (area x EF, by climate region, Table 5.4). The SOC side of Table 5.3 is
handled by the caller passing FLU = 0.80 for a rewetted state; this module adds the second 20-year
step (years 21-40 after rewetting) that takes SOC on to FLU = 1.0.
"""

from .general_functions import compute_half_year_cumulative_n_year_maturity
from .ghg_emissions_classes import ActivityTypes, Emission, GasTypes, YearlyGasActivityEmissionSet
from .ghg_inventory_class import InventoryPerGasPerActivity


def calculate_iwms_rewetting(module) -> None:
    """Append rewetting CH4 and the 21-40 year SOC gain to a land module's result and inventory.

    A land math module carries one cohort: hectares_start > 0 is land leaving the start state,
    otherwise it is land arriving in the end state. CH4 applies while that cohort's state is rewetted.
    """
    if not (module.iwms_rewetted_start or module.iwms_rewetted_end):
        return

    rewetted = module.iwms_rewetted_start if module.hectares_start > 0 else module.iwms_rewetted_end
    t_co2e_per_ha = module.ef_ch4_iwms * module.methane_constant / 1000

    if rewetted:
        yearly = [ha * t_co2e_per_ha for ha in module.hectares_total]
        module.result.yearly_emissions_by_sector_by_gas.append(
            YearlyGasActivityEmissionSet(0, GasTypes.CH4, [Emission(e, GasTypes.CH4) for e in yearly], ActivityTypes.IWMS_REWETTING_CH4, delay=module.delay)
        )

    inventory_value = module.hectares_start * t_co2e_per_ha if module.iwms_rewetted_start else 0
    module.inventory.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(GasTypes.CH4, inventory_value, ActivityTypes.IWMS_REWETTING_CH4))

    # Land already rewetted at the start is past an unknown part of the 40 years, so only a fresh rewetting gets the second step.
    if module.calculate_soc_som and module.iwms_rewetted_end and not module.iwms_rewetted_start and module.soc_end_iwms_after_40 is not None:
        _append_soc_years_21_40(module)


def _append_soc_years_21_40(module) -> None:
    delta_co2_per_ha_per_yr = -(module.soc_end_iwms_after_40 - module.soc_end) / 20 * (44 / 12)

    before_40, _ = compute_half_year_cumulative_n_year_maturity(
        module.hectares_start, module.hectares_end, module.implementation_time, module.capitalization_time, module.rate_type, number_of_years=40
    )
    hectares_21_40 = [max(a - b, 0) for a, b in zip(before_40, module.hectares_before_20)]
    yearly = [ha * delta_co2_per_ha_per_yr for ha in hectares_21_40]

    module.result.yearly_emissions_by_sector_by_gas.append(
        YearlyGasActivityEmissionSet(0, GasTypes.CO2, [Emission(e, GasTypes.CO2) for e in yearly], ActivityTypes.SOIL_CO2_CHANGE, delay=module.delay)
    )
