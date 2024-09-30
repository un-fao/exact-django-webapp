from types import SimpleNamespace

import ipcc.models as ipcc

import api.calculators as calcs
import api.models as api
import api.serializers as serializers
import api.utilities as utils


# Create a base class that all other classes inherit from
class Defaults:
    def __init__(self, input: api.Module):
        self.input = input
        self.values = SimpleNamespace()
        self.activity = input.parent.activity if getattr(input, "parent", None) else input.activity
        self.climate: api.Climate = self.activity.climate_t2 if self.activity.climate_t2 else self.activity.project.climate
        self.moisture: api.Moisture = self.activity.moisture_t2 if self.activity.moisture_t2 else self.activity.project.moisture
        self.soil_type: api.SoilType = self.activity.project.soil_type

        self.module_start = self.module_w = self.module_wo = self.input
        luc = getattr(self.input, "land_use_change", None)
        if luc:
            self.module_start, self.module_w, self.module_wo = calcs.get_luc_modules(luc)

    def get_defaults(self, calculate=False) -> dict:
        """
        Gets the default tier2 values for a given module.
        """
        raise NotImplementedError(f"get_defaults() method must be implemented for {self.__class__.__name__}.")


class DefaultsFactory:
    """
    Factory class to create a Defaults object for a given module.
    """

    @staticmethod
    def get_defaults(input: api.Module, calculate=False) -> Defaults:
        """
        Creates a Defaults object for a given module.
        """

        module_type = type(input).__name__
        DefaultClass: Defaults = globals().get(f"{module_type}Defaults", None)

        if DefaultClass is not None:

            if not input.is_ready():
                return DefaultClass(input).values

            return DefaultClass(input).get_defaults(calculate=calculate)
        else:
            raise NotImplementedError(f"Defaults for {module_type} have not been implemented.")


class GrasslandDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
            combustion_factor_t2_start_default=0,
            combustion_factor_t2_w_default=0,
            combustion_factor_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        """
        Gets the default tier2 values for a Grassland module.
        """
        self.input: api.Grassland

        defaults = calcs.GrasslandCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            biomass_t2_start_default=defaults.agb.value,
            biomass_t2_w_default=defaults.agb.value,
            biomass_t2_wo_default=defaults.agb.value,
            combustion_factor_t2_start_default=defaults.cf.value,
            combustion_factor_t2_w_default=defaults.cf.value,
            combustion_factor_t2_wo_default=defaults.cf.value,
        )


class AnnualCroplandDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
            residue_availability_t2_start_default=0,
            residue_availability_t2_w_default=0,
            residue_availability_t2_wo_default=0,
            minor_biomass_t2_start_default=0,
            minor_biomass_t2_w_default=0,
            minor_biomass_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:

        self.input: api.AnnualCropland

        defaults = calcs.AnnualCropCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            biomass_t2_start_default=defaults.biomass_ef_start.value,
            biomass_t2_w_default=defaults.biomass_ef_w.value,
            biomass_t2_wo_default=defaults.biomass_ef_wo.value,
            residue_availability_t2_start_default=defaults.residue_availability_t2_start.value,
            residue_availability_t2_w_default=defaults.residue_availability_t2_w.value,
            residue_availability_t2_wo_default=defaults.residue_availability_t2_wo.value,
            minor_residue_t2_start_default=defaults.minor_residue_availability_t2_start.value,
            minor_residue_t2_w_default=defaults.minor_residue_availability_t2_w.value,
            minor_residue_t2_wo_default=defaults.minor_residue_availability_t2_wo.value,
            minor_biomass_t2_start_default=defaults.minor_biomass_start.value,
            minor_biomass_t2_w_default=defaults.minor_biomass_w.value,
            minor_biomass_t2_wo_default=defaults.minor_biomass_wo.value,
        )


class PerennialCroplandDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            agb_t2_start_default=0,
            agb_t2_w_default=0,
            agb_t2_wo_default=0,
            agb_max_t2_start_default=0,
            agb_max_t2_w_default=0,
            agb_max_t2_wo_default=0,
            bgb_t2_start_default=0,
            bgb_t2_w_default=0,
            bgb_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            residue_burned_t2_start_default=0,
            residue_burned_t2_w_default=0,
            residue_burned_t2_wo_default=0,
            fire_periodicity_t2_start_default=0,
            fire_periodicity_t2_w_default=0,
            fire_periodicity_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.PerennialCropland

        defaults = calcs.PerennialCropCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            agb_t2_start_default=defaults.ag_default_start.value,
            agb_t2_w_default=defaults.ag_default_w.value,
            agb_t2_wo_default=defaults.ag_default_wo.value,
            agb_max_t2_start_default=defaults.agb_max_c_start.value,
            agb_max_t2_w_default=defaults.agb_max_c_w.value,
            agb_max_t2_wo_default=defaults.agb_max_c_wo.value,
            bgb_t2_start_default=defaults.bg_default_start.value,
            bgb_t2_w_default=defaults.bg_default_w.value,
            bgb_t2_wo_default=defaults.bg_default_wo.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            fire_periodicity_t2_start_default=defaults.default_fire_periodicity.value,
            fire_periodicity_t2_w_default=defaults.default_fire_periodicity.value,
            fire_periodicity_t2_wo_default=defaults.default_fire_periodicity.value,
            biomass_t2_start_default=defaults.biomass_ef_start.value,
            biomass_t2_w_default=defaults.biomass_ef_w.value,
            biomass_t2_wo_default=defaults.biomass_ef_wo.value,
            residue_availability_t2_start_default=defaults.residue_availability_t2_start.value,
            residue_availability_t2_w_default=defaults.residue_availability_t2_w.value,
            residue_availability_t2_wo_default=defaults.residue_availability_t2_wo.value,
        )


class FloodedRiceDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            efc_t2_start_default=0,
            efc_t2_w_default=0,
            efc_t2_wo_default=0,
            sfw_t2_start_default=0,
            sfw_t2_w_default=0,
            sfw_t2_wo_default=0,
            sfp_t2_start_default=0,
            sfp_t2_w_default=0,
            sfp_t2_wo_default=0,
            efi_t2_start_default=0,
            efi_t2_w_default=0,
            efi_t2_wo_default=0,
            rice_straw_t2_start_defaults=0,
            rice_straw_t2_w_defaults=0,
            rice_straw_t2_wo_defaults=0,
            crop_yield_t2_start_default=0,
            crop_yield_t2_w_default=0,
            crop_yield_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.FloodedRice

        defaults = calcs.FloodedRiceSeasonCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            # TODO: Biomass will be yield+rice_straw (to be included in the model)
            biomass_t2_start_default=defaults.biomass_ef_start.value,
            biomass_t2_w_default=defaults.biomass_ef_w.value,
            biomass_t2_wo_default=defaults.biomass_ef_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            efc_t2_start_default=defaults.efc.value,
            efc_t2_w_default=defaults.efc.value,
            efc_t2_wo_default=defaults.efc.value,
            sfw_t2_start_default=defaults.sfw_start.value,
            sfw_t2_w_default=defaults.sfw_w.value,
            sfw_t2_wo_default=defaults.sfw_wo.value,
            sfp_t2_start_default=defaults.sfp_start.value,
            sfp_t2_w_default=defaults.sfp_w.value,
            sfp_t2_wo_default=defaults.sfp_wo.value,
            efi_t2_start_default=defaults.efi_start.value,
            efi_t2_w_default=defaults.efi_w.value,
            efi_t2_wo_default=defaults.efi_wo.value,
            rice_straw_t2_start_defaults=defaults.sfo_start.value,
            rice_straw_t2_w_defaults=defaults.sfo_w.value,
            rice_straw_t2_wo_defaults=defaults.sfo_wo.value,
            crop_yield_t2_start_default=defaults.yield_ref.value,
            crop_yield_t2_w_default=defaults.yield_ref.value,
            crop_yield_t2_wo_default=defaults.yield_ref.value,
        )


class LivestockDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            enteric_fermentation_t2_start_default=0,
            enteric_fermentation_t2_w_default=0,
            enteric_fermentation_t2_wo_default=0,
            prp_percentage_t2_start_default=0,
            prp_percentage_t2_w_default=0,
            prp_percentage_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Livestock

        defaults = calcs.LivestockCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            enteric_fermentation_t2_start_default=defaults.enteric_ch4_start.value,
            enteric_fermentation_t2_w_default=defaults.enteric_ch4_w.value,
            enteric_fermentation_t2_wo_default=defaults.enteric_ch4_wo.value,
            prp_percentage_t2_start_default=defaults.animal_waste_prp_start.value,
            prp_percentage_t2_w_default=defaults.animal_waste_prp_w.value,
            prp_percentage_t2_wo_default=defaults.animal_waste_prp_wo.value,
            # TODO: Wait for Lorenzo to communicate which fields to get from math model
            # self.ch4_prp_head_start_tier_2_default = None
            # self.ch4_prp_head_end_tier_2_default = None
            # self.ch4_system_head_start_tier_2_default = None
            # self.ch4_system_head_end_tier_2_default = None
            # self.n2o_prp_direct_head_start_tier_2_default = None
            # self.n2o_prp_direct_head_end_tier_2_default = None
            # self.n2o_system_direct_head_start_tier_2_default = None
            # self.n2o_system_direct_head_end_tier_2_default = None
        )


class ElectricityDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_source_default=0,
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
            transmission_loss_start_default=0,
            transmission_loss_w_default=0,
            transmission_loss_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Electricity

        defaults = calcs.ElectricityCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ef_source_default=defaults.ef_source,
            ef_t2_start_default=defaults.ef_country,
            ef_t2_w_default=defaults.ef_country,
            ef_t2_wo_default=defaults.ef_country,
            transmission_loss_start_default=defaults.transmission_loss,
            transmission_loss_w_default=defaults.transmission_loss,
            transmission_loss_wo_default=defaults.transmission_loss,
        )


class FuelDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Fuel

        defaults = calcs.FuelCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return self.values


class InputEntryDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            co2_emissions_t2_default=None,
            n2o_emissions_t2_default=None,
            co2_e_emissions_t2_default=None,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.InputEntry

        defaults = calcs.InputEntryCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        if defaults.ef:
            if defaults.ef.co2_value:
                self.values.co2_emissions_t2_default = defaults.ef.co2_value
            if defaults.ef.n2o_value:
                self.values.n2o_emissions_t2_default = defaults.ef.n2o_value
            if defaults.ef.co2_eq_value:
                self.values.co2_e_emissions_t2_default = defaults.ef.co2_eq_value

        return self.values


class LargeFisheryDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            energy_emission_factor_t2_start_default=0,
            energy_emission_factor_t2_w_default=0,
            energy_emission_factor_t2_wo_default=0,
            refrigerant_lost_per_tonne_t2_start_default=0,
            refrigerant_lost_per_tonne_t2_w_default=0,
            refrigerant_lost_per_tonne_t2_wo_default=0,
            refrigerant_gwp_t2_start_default=0,
            refrigerant_gwp_t2_w_default=0,
            refrigerant_gwp_t2_wo_default=0,
            tonnes_of_ice_t2_start_default=0,
            tonnes_of_ice_t2_w_default=0,
            tonnes_of_ice_t2_wo_default=0,
            inshore_ice_production_kwh_per_tonne_t2_start_default=0,
            inshore_ice_production_kwh_per_tonne_t2_w_default=0,
            inshore_ice_production_kwh_per_tonne_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.LargeFishery

        defaults = calcs.LargeFisheryCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            energy_emission_factor_t2_start_default=defaults.ef_diesel_default,
            energy_emission_factor_t2_w_default=defaults.ef_diesel_default,
            energy_emission_factor_t2_wo_default=defaults.ef_diesel_default,
            refrigerant_lost_per_tonne_t2_start_default=defaults.lost_refrigerant_default,
            refrigerant_lost_per_tonne_t2_w_default=defaults.lost_refrigerant_default,
            refrigerant_lost_per_tonne_t2_wo_default=defaults.lost_refrigerant_default,
            refrigerant_gwp_t2_start_default=self.input.refrigerant_gwp,
            refrigerant_gwp_t2_w_default=self.input.refrigerant_gwp,
            refrigerant_gwp_t2_wo_default=self.input.refrigerant_gwp,
            tonnes_of_ice_t2_start_default=defaults.tonnes_ice_default,
            tonnes_of_ice_t2_w_default=defaults.tonnes_ice_default,
            tonnes_of_ice_t2_wo_default=defaults.tonnes_ice_default,
            inshore_ice_production_kwh_per_tonne_t2_start_default=defaults.kw_tonnes,
            inshore_ice_production_kwh_per_tonne_t2_w_default=defaults.kw_tonnes,
            inshore_ice_production_kwh_per_tonne_t2_wo_default=defaults.kw_tonnes,
        )


class SmallFisheryDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            energy_emission_factor_t2_start_default=0,
            energy_emission_factor_t2_w_default=0,
            energy_emission_factor_t2_wo_default=0,
            refrigerant_lost_per_tonne_t2_start_default=0,
            refrigerant_lost_per_tonne_t2_w_default=0,
            refrigerant_lost_per_tonne_t2_wo_default=0,
            refrigerant_gwp_t2_start_default=0,
            refrigerant_gwp_t2_w_default=0,
            refrigerant_gwp_t2_wo_default=0,
            tonnes_of_ice_t2_start_default=0,
            tonnes_of_ice_t2_w_default=0,
            tonnes_of_ice_t2_wo_default=0,
            inshore_ice_production_kwh_per_tonne_t2_start_default=0,
            inshore_ice_production_kwh_per_tonne_t2_w_default=0,
            inshore_ice_production_kwh_per_tonne_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.SmallFishery

        defaults = calcs.SmallFisheryCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            energy_emission_factor_t2_start_default=defaults.ef_diesel_default,
            energy_emission_factor_t2_w_default=defaults.ef_diesel_default,
            energy_emission_factor_t2_wo_default=defaults.ef_diesel_default,
            refrigerant_lost_per_tonne_t2_start_default=defaults.lost_refrigerant_default,
            refrigerant_lost_per_tonne_t2_w_default=defaults.lost_refrigerant_default,
            refrigerant_lost_per_tonne_t2_wo_default=defaults.lost_refrigerant_default,
            refrigerant_gwp_t2_start_default=self.input.refrigerant_gwp,
            refrigerant_gwp_t2_w_default=self.input.refrigerant_gwp,
            refrigerant_gwp_t2_wo_default=self.input.refrigerant_gwp,
            tonnes_of_ice_t2_start_default=defaults.tonnes_ice_default,
            tonnes_of_ice_t2_w_default=defaults.tonnes_ice_default,
            tonnes_of_ice_t2_wo_default=defaults.tonnes_ice_default,
            inshore_ice_production_kwh_per_tonne_t2_start_default=defaults.kw_tonnes,
            inshore_ice_production_kwh_per_tonne_t2_w_default=defaults.kw_tonnes,
            inshore_ice_production_kwh_per_tonne_t2_wo_default=defaults.kw_tonnes,
        )


class IrrigationSystemDefaults(Defaults):

    def __init__(self, input: calcs.IrrigationSystem):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.IrrigationSystem

        defaults = calcs.IrrigationSystemCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ef_t2_start_default=defaults.ef.value,
            ef_t2_w_default=defaults.ef.value,
            ef_t2_wo_default=defaults.ef.value,
        )


class IrrigationPhaseDefaults(Defaults):

    def __init__(self, input: calcs.IrrigationPhase):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.IrrigationPhase

        defaults = calcs.IrrigationPhaseCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ef_t2_start_default=defaults.ef.value,
            ef_t2_w_default=defaults.ef.value,
            ef_t2_wo_default=defaults.ef.value,
        )


class SettlementDefaults(Defaults):
    def __init__(self, input: calcs.Settlement):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            agb_t2_start_default=0,
            agb_t2_w_default=0,
            agb_t2_wo_default=0,
            bgb_t2_start_default=0,
            bgb_t2_w_default=0,
            bgb_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Settlement

        defaults = calcs.SettlementCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            agb_t2_start_default=defaults.ef_start.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
            agb_t2_w_default=defaults.ef_w.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
            agb_t2_wo_default=defaults.ef_wo.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
            bgb_t2_start_default=defaults.ef_start.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
            bgb_t2_w_default=defaults.ef_w.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
            bgb_t2_wo_default=defaults.ef_wo.biomass,  # TODO: Tell @Peter about agb/bgb implementation for NotCultivatedLand model
        )


class CoastalWetlandDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            agb_t2_start_default=0,
            agb_t2_w_default=0,
            agb_t2_wo_default=0,
            bgb_t2_start_default=0,
            bgb_t2_w_default=0,
            bgb_t2_wo_default=0,
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            pc_c_lost_after_excavation_t2_start_default=0,
            pc_c_lost_after_excavation_t2_w_default=0,
            pc_c_lost_after_excavation_t2_wo_default=0,
            drainage_ef_t2_start_default=0,
            drainage_ef_t2_w_default=0,
            drainage_ef_t2_wo_default=0,
            co2_rewetting_t2_start_default=0,
            co2_rewetting_t2_w_default=0,
            co2_rewetting_t2_wo_default=0,
            ch4_rewetting_t2_start_default=0,
            ch4_rewetting_t2_w_default=0,
            ch4_rewetting_t2_wo_default=0,
            avg_salinity_t2_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.CoastalWetland

        defaults = calcs.CoastalWetlandCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            agb_t2_start_default=defaults.agb.value,
            agb_t2_w_default=defaults.agb.value,
            agb_t2_wo_default=defaults.agb.value,
            bgb_t2_start_default=defaults.bgb.value,
            bgb_t2_w_default=defaults.bgb.value,
            bgb_t2_wo_default=defaults.bgb.value,
            soc_t2_start_default=defaults.soil_1m.value,
            soc_t2_w_default=defaults.soil_1m.value,
            soc_t2_wo_default=defaults.soil_1m.value,
            pc_c_lost_after_excavation_t2_start_default=defaults.pc_c_lost_excavation.value,
            pc_c_lost_after_excavation_t2_w_default=defaults.pc_c_lost_excavation.value,
            pc_c_lost_after_excavation_t2_wo_default=defaults.pc_c_lost_excavation.value,
            drainage_ef_t2_start_default=defaults.ef_drainage.value,
            drainage_ef_t2_w_default=defaults.ef_drainage.value,
            drainage_ef_t2_wo_default=defaults.ef_drainage.value,
            co2_rewetting_t2_start_default=defaults.rewetting_c.value,
            co2_rewetting_t2_w_default=defaults.rewetting_c.value,
            co2_rewetting_t2_wo_default=defaults.rewetting_c.value,
            ch4_rewetting_t2_start_default=defaults.rewetting_ch4.value,
            ch4_rewetting_t2_w_default=defaults.rewetting_ch4.value,
            ch4_rewetting_t2_wo_default=defaults.rewetting_ch4.value,
        )


class WaterbodyDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ch4_ef_t2_start_default=0,
            ch4_ef_t2_w_default=0,
            ch4_ef_t2_wo_default=0,
            alpha_t2_start_default=0,
            alpha_t2_w_default=0,
            alpha_t2_wo_default=0,
            mean_annual_t2_start_default=0,
            mean_annual_t2_w_default=0,
            mean_annual_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Waterbody

        defaults = calcs.WaterbodyCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ch4_ef_t2_start_default=defaults.methane_emission_factor.value,
            ch4_ef_t2_w_default=defaults.methane_emission_factor.value,
            ch4_ef_t2_wo_default=defaults.methane_emission_factor.value,
            alpha_t2_start_default=defaults.trophic_state_start.value,
            alpha_t2_w_default=defaults.trophic_state_w.value,
            alpha_t2_wo_default=defaults.trophic_state_wo.value,
            mean_annual_t2_start_default=defaults.trophic_state_start.chloa,
            mean_annual_t2_w_default=defaults.trophic_state_w.chloa,
            mean_annual_t2_wo_default=defaults.trophic_state_wo.chloa,
        )


class OrganicSoilDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            onsite_co2_drainage_t2_start_default=0,
            onsite_co2_drainage_t2_w_default=0,
            onsite_co2_drainage_t2_wo_default=0,
            onsite_ch4_drainage_t2_start_default=0,
            onsite_ch4_drainage_t2_w_default=0,
            onsite_ch4_drainage_t2_wo_default=0,
            onsite_n2o_drainage_t2_start_default=0,
            onsite_n2o_drainage_t2_w_default=0,
            onsite_n2o_drainage_t2_wo_default=0,
            offsite_doc_drainage_t2_start_default=0,
            offsite_doc_drainage_t2_w_default=0,
            offsite_doc_drainage_t2_wo_default=0,
            offsite_ch4_drainage_t2_start_default=0,
            offsite_ch4_drainage_t2_w_default=0,
            offsite_ch4_drainage_t2_wo_default=0,
            onsite_co2_rewetting_t2_start_default=0,
            onsite_co2_rewetting_t2_w_default=0,
            onsite_co2_rewetting_t2_wo_default=0,
            onsite_ch4_rewetting_t2_start_default=0,
            onsite_ch4_rewetting_t2_w_default=0,
            onsite_ch4_rewetting_t2_wo_default=0,
            onsite_n2o_rewetting_t2_start_default=0,
            onsite_n2o_rewetting_t2_w_default=0,
            onsite_n2o_rewetting_t2_wo_default=0,
            offsite_doc_rewetting_t2_start_default=0,
            offsite_doc_rewetting_t2_w_default=0,
            offsite_doc_rewetting_t2_wo_default=0,
            mean_dry_matter_t2_start_default=0,
            mean_dry_matter_t2_w_default=0,
            mean_dry_matter_t2_wo_default=0,
            fire_on_soil_co2_t2_start_default=0,
            fire_on_soil_co2_t2_w_default=0,
            fire_on_soil_co2_t2_wo_default=0,
            fire_on_soil_co_t2_start_default=0,
            fire_on_soil_co_t2_w_default=0,
            fire_on_soil_co_t2_wo_default=0,
            fire_on_soil_ch4_t2_start_default=0,
            fire_on_soil_ch4_t2_w_default=0,
            fire_on_soil_ch4_t2_wo_default=0,
            onsite_co2_peat_t2_start_default=0,
            onsite_co2_peat_t2_w_default=0,
            onsite_co2_peat_t2_wo_default=0,
            onsite_n2o_peat_t2_start_default=0,
            onsite_n2o_peat_t2_w_default=0,
            onsite_n2o_peat_t2_wo_default=0,
            offsite_doc_peat_t2_start_default=0,
            offsite_doc_peat_t2_w_default=0,
            offsite_doc_peat_t2_wo_default=0,
            offsite_ch4_peat_t2_start_default=0,
            offsite_ch4_peat_t2_w_default=0,
            offsite_ch4_peat_t2_wo_default=0,
            peat_density_t2_start_default=0,
            peat_density_t2_w_default=0,
            peat_density_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.OrganicSoil

        defaults = calcs.OrganicSoilCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            onsite_co2_drainage_t2_start_default=defaults.ef_onsite_start.co2,
            onsite_co2_drainage_t2_w_default=defaults.ef_onsite_w.co2,
            onsite_co2_drainage_t2_wo_default=defaults.ef_onsite_wo.co2,
            onsite_ch4_drainage_t2_start_default=defaults.ef_onsite_start.ch4,
            onsite_ch4_drainage_t2_w_default=defaults.ef_onsite_w.ch4,
            onsite_ch4_drainage_t2_wo_default=defaults.ef_onsite_wo.ch4,
            onsite_n2o_drainage_t2_start_default=defaults.ef_onsite_start.n2o,
            onsite_n2o_drainage_t2_w_default=defaults.ef_onsite_w.n2o,
            onsite_n2o_drainage_t2_wo_default=defaults.ef_onsite_wo.n2o,
            offsite_doc_drainage_t2_start_default=defaults.ef_offsite_start.doc,
            offsite_doc_drainage_t2_w_default=defaults.ef_offsite_w.doc,
            offsite_doc_drainage_t2_wo_default=defaults.ef_offsite_wo.doc,
            offsite_ch4_drainage_t2_start_default=defaults.ef_offsite_start.ch4,
            offsite_ch4_drainage_t2_w_default=defaults.ef_offsite_w.ch4,
            offsite_ch4_drainage_t2_wo_default=defaults.ef_offsite_wo.ch4,
            onsite_co2_rewetting_t2_start_default=defaults.rewetting_start.co2,
            onsite_co2_rewetting_t2_w_default=defaults.rewetting_w.co2,
            onsite_co2_rewetting_t2_wo_default=defaults.rewetting_wo.co2,
            onsite_ch4_rewetting_t2_start_default=defaults.rewetting_start.ch4,
            onsite_ch4_rewetting_t2_w_default=defaults.rewetting_w.ch4,
            onsite_ch4_rewetting_t2_wo_default=defaults.rewetting_wo.ch4,
            onsite_n2o_rewetting_t2_start_default=defaults.rewetting_start.n2o,
            onsite_n2o_rewetting_t2_w_default=defaults.rewetting_w.n2o,
            onsite_n2o_rewetting_t2_wo_default=defaults.rewetting_wo.n2o,
            offsite_doc_rewetting_t2_start_default=defaults.rewetting_start.doc,
            offsite_doc_rewetting_t2_w_default=defaults.rewetting_w.doc,
            offsite_doc_rewetting_t2_wo_default=defaults.rewetting_wo.doc,
            mean_dry_matter_t2_start_default=0,
            mean_dry_matter_t2_w_default=defaults.dry_matter_w.value,
            mean_dry_matter_t2_wo_default=defaults.dry_matter_wo.value,
            fire_on_soil_co2_t2_start_default=defaults.fire_ref.co2,
            fire_on_soil_co2_t2_w_default=defaults.fire_ref.co2,
            fire_on_soil_co2_t2_wo_default=defaults.fire_ref.co2,
            fire_on_soil_co_t2_start_default=defaults.fire_ref.co,
            fire_on_soil_co_t2_w_default=defaults.fire_ref.co,
            fire_on_soil_co_t2_wo_default=defaults.fire_ref.co,
            fire_on_soil_ch4_t2_start_default=defaults.fire_ref.ch4,
            fire_on_soil_ch4_t2_w_default=defaults.fire_ref.ch4,
            fire_on_soil_ch4_t2_wo_default=defaults.fire_ref.ch4,
            onsite_co2_peat_t2_start_default=0,
            onsite_co2_peat_t2_w_default=defaults.onsite_ef_w.co2,
            onsite_co2_peat_t2_wo_default=defaults.onsite_ef_wo.co2,
            onsite_n2o_peat_t2_start_default=0,
            onsite_n2o_peat_t2_w_default=defaults.onsite_ef_w.n2o,
            onsite_n2o_peat_t2_wo_default=defaults.onsite_ef_wo.n2o,
            offsite_doc_peat_t2_start_default=0,
            offsite_doc_peat_t2_w_default=defaults.offsite_ef_w.doc,
            offsite_doc_peat_t2_wo_default=defaults.offsite_ef_wo.doc,
            offsite_ch4_peat_t2_start_default=0,
            offsite_ch4_peat_t2_w_default=defaults.offsite_ef_w.ch4,
            offsite_ch4_peat_t2_wo_default=defaults.offsite_ef_wo.ch4,
            # TODO: Ask Lorenzo about mapping of commented out fields
            # peat_density_t2_start_default=defaults.peat_density.value, # TODO: Ask @Peter m/V
            # peat_density_t2_w_default=defaults.peat_density.value, # TODO: Ask @Peter m/V
            # peat_density_t2_wo_default=defaults.peat_density.value, # TODO: Ask @Peter m/V
        )


class AquacultureDefaults(Defaults):

    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            electricity_used_t2_start_default=0,
            electricity_used_t2_w_default=0,
            electricity_used_t2_wo_default=0,
            electricity_ef_t2_start_default=0,
            electricity_ef_t2_w_default=0,
            electricity_ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Aquaculture

        defaults = calcs.AquacultureCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            electricity_used_t2_start_default=defaults.elec.operating_margin,
            electricity_used_t2_w_default=defaults.elec.operating_margin,
            electricity_used_t2_wo_default=defaults.elec.operating_margin,
            electricity_ef_t2_start_default=defaults.NITROUS_EF_DEFAULT,
            electricity_ef_t2_w_default=defaults.NITROUS_EF_DEFAULT,
            electricity_ef_t2_wo_default=defaults.NITROUS_EF_DEFAULT,
        )


class OtherLandDefaults(Defaults):  # TODO: Rename to OtherLand
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            agb_t2_start_default=0,
            agb_t2_w_default=0,
            agb_t2_wo_default=0,
            bgb_t2_start_default=0,
            bgb_t2_w_default=0,
            bgb_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.OtherLand

        defaults = calcs.OtherLandCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            # TODO: Ask Lorenzo about mapping of commented out fields
            # agb_t2_start_default=defaults.agb_start.value,
            # agb_t2_w_default=defaults.agb_w.value,
            # agb_t2_wo_default=defaults.agb_wo.value,
            # bgb_t2_start_default=defaults.bgb_start.value,
            # bgb_t2_w_default=defaults.bgb_w.value,
            # bgb_t2_wo_default=defaults.bgb_wo.value,
            # biomass_t2_start_default=defaults.biomass_start.value,
            # biomass_t2_w_default=defaults.biomass_w.value,
            # biomass_t2_wo_default=defaults.biomass_wo.value,
        )


class RoadDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Road

        defaults = calcs.RoadCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ef_t2_start_default=defaults.ef.value,
            ef_t2_w_default=defaults.ef.value,
            ef_t2_wo_default=defaults.ef.value,
        )


class BuildingDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Building

        defaults = calcs.BuildingCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            ef_t2_start_default=defaults.ef.value,
            ef_t2_w_default=defaults.ef.value,
            ef_t2_wo_default=defaults.ef.value,
        )


class SetAsideDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            soc_t2_start_default=0,
            soc_t2_w_default=0,
            soc_t2_wo_default=0,
            flu_t2_start_default=0,
            flu_t2_w_default=0,
            flu_t2_wo_default=0,
            fi_t2_start_default=0,
            fi_t2_w_default=0,
            fi_t2_wo_default=0,
            fmg_t2_start_default=0,
            fmg_t2_w_default=0,
            fmg_t2_wo_default=0,
            agb_t2_start_default=0,
            agb_t2_w_default=0,
            agb_t2_wo_default=0,
            bgb_t2_start_default=0,
            bgb_t2_w_default=0,
            bgb_t2_wo_default=0,
            biomass_t2_start_default=0,
            biomass_t2_w_default=0,
            biomass_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.SetAside

        defaults = calcs.SetAsideCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            fi_t2_start_default=defaults.fi_start.value,
            fi_t2_w_default=defaults.fi_w.value,
            fi_t2_wo_default=defaults.fi_wo.value,
            fmg_t2_start_default=defaults.fmg_start.value,
            fmg_t2_w_default=defaults.fmg_w.value,
            fmg_t2_wo_default=defaults.fmg_wo.value,
            # TODO: Ask Lorenzo about mapping of commented out fields
            # agb_t2_start_default=defaults.agb_start.value,
            # agb_t2_w_default=defaults.agb_w.value,
            # agb_t2_wo_default=defaults.agb_wo.value,
            # bgb_t2_start_default=defaults.bgb_start.value,
            # bgb_t2_w_default=defaults.bgb_w.value,
            # bgb_t2_wo_default=defaults.bgb_wo.value,
            # biomass_t2_start_default=defaults.biomass_start.value,
            # biomass_t2_w_default=defaults.biomass_w.value,
            # biomass_t2_wo_default=defaults.biomass_wo.value,
        )


class EnergyDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Energy

        defaults = calcs.EnergyCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace()


class IrrigationDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            ef_t2_start_default=0,
            ef_t2_w_default=0,
            ef_t2_wo_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Irrigation

        defaults = calcs.IrrigationCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace()


class InputDefaults(Defaults):
    def __init__(self, input: calcs.Module):
        super().__init__(input)

        self.values = SimpleNamespace(
            co2_emissions_t2_default=0,
            n2o_emissions_t2_default=0,
            co2_e_emissions_t2_default=0,
        )

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.Input

        defaults = calcs.InputCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace()
