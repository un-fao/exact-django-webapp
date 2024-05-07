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

        match type(input):
            case api.Grassland:
                return GrasslandDefaults(input).get_defaults(calculate=calculate)
            case api.AnnualCropping:
                return AnnualCroppingDefaults(input).get_defaults(calculate=calculate)
            case api.PerennialCropping:
                return PerennialCroppingDefaults(input).get_defaults(calculate=calculate)
            case api.FloodedRice:
                return FloodedRiceDefaults(input).get_defaults(calculate=calculate)
            case _:
                raise NotImplementedError(f"Defaults for {input.__class__.__name__} have not been implemented.")


class GrasslandDefaults(Defaults):

    def get_defaults(self, calculate=False) -> dict:
        """
        Gets the default tier2 values for a Grassland module.
        """
        self.input: api.Grassland  # type hinting

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


class AnnualCroppingDefaults(Defaults):
    pass

    def get_defaults(self, calculate=False) -> dict:
        self.input: api.AnnualCropping

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
            biomass_t2_start_default=defaults.biomass_start.value,
            biomass_t2_w_default=defaults.biomass_w.value,
            biomass_t2_wo_default=defaults.biomass_wo.value,
            minor_biomass_t2_start_default=defaults.minor_biomass_start.value,
            minor_biomass_t2_w_default=defaults.minor_biomass_w.value,
            minor_biomass_t2_wo_default=defaults.minor_biomass_wo.value,
        )


class PerennialCroppingDefaults(Defaults):
    def get_defaults(self, calculate=False) -> dict:
        self.input: api.PerennialCropping

        defaults = calcs.PerennialCropCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
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
            residue_burned_t2_start_default=defaults.residue_burned_t2_start.value,
            residue_burned_t2_w_default=defaults.residue_burned_t2_w.value,
            residue_burned_t2_wo_default=defaults.residue_burned_t2_wo.value,
            fire_periodicity_t2_start_default=defaults.default_fire_periodicity.value,
            fire_periodicity_t2_w_default=defaults.default_fire_periodicity.value,
            fire_periodicity_t2_wo_default=defaults.default_fire_periodicity.value,
        )


class FloodedRiceDefaults(Defaults):
    def get_defaults(self, calculate=False) -> dict:
        self.input: api.FloodedRice

        defaults = calcs.FloodedRiceSeasonCalculator(self.input)
        defaults.get_defaults(calculate=calculate)

        return SimpleNamespace(
            # TODO: Ask Lorenzo about mapping of commented out fields
            soc_t2_start_default=defaults.soc.value,
            soc_t2_w_default=defaults.soc.value,
            soc_t2_wo_default=defaults.soc.value,
            flu_t2_start_default=defaults.flu_start.value,
            flu_t2_w_default=defaults.flu_w.value,
            flu_t2_wo_default=defaults.flu_wo.value,
            # TODO: Biomass will be yield+rice_straw (to be included in the model)
            # biomass_t2_start_default=defaults.yield_ref.value,
            # biomass_t2_w_default=defaults.yield_ref.value,
            # biomass_t2_wo_default=defaults.yield_ref.value,
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
        )
