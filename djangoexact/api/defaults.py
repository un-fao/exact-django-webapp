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

    def get_defaults() -> dict:
        """
        Gets the default tier2 values for a given module.
        """
        pass


class DefaultsFactory:
    """
    Factory class to create a Defaults object for a given module.
    """

    @staticmethod
    def get_defaults(input: api.Module, calculate=False) -> Defaults:
        """
        Creates a Defaults object for a given module.
        """

        if isinstance(input, api.Grassland):
            return GrasslandDefaults(input).get_defaults(calculate=calculate)
        elif isinstance(input, api.AnnualCropping):
            return AnnualCroppingDefaults(input).get_defaults(calculate=calculate)
        else:
            try:
                getattr(api, input.__class__.__name__)
            except AttributeError:
                raise ValueError("Invalid module type.")

            raise NotImplementedError(f"Defaults for {input.__class__.__name__} have not been implemented.")


class GrasslandDefaults(Defaults):

    def get_defaults(self, calculate=False) -> dict:
        """
        Gets the default tier2 values for a Grassland module.
        """
        self.input: api.Grassland  # type hinting

        # TODO: This can be generalized even more by directly returning a simplenamespace from the calculator
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
