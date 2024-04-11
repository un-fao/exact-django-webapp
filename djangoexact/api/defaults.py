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
    def get_defaults(input: api.Module) -> Defaults:
        """
        Creates a Defaults object for a given module.
        """

        if isinstance(input, api.Grassland):
            return GrasslandDefaults(input).get_defaults()
        elif isinstance(input, api.AnnualCropping):
            return AnnualCroppingDefaults(input).get_defaults()
        else:
            try:
                getattr(api, input.__class__.__name__)
            except AttributeError:
                raise ValueError("Invalid module type.")

            raise NotImplementedError(f"Defaults for {input.__class__.__name__} have not been implemented.")


class GrasslandDefaults(Defaults):

    def get_defaults(self) -> dict:
        """
        Gets the default tier2 values for a Grassland module.
        """
        self.input: api.Grassland  # type hinting

        soc_t2_start_default = 0
        soc_t2_w_default = 0
        soc_t2_wo_default = 0

        biomass_t2_start_default = 0
        biomass_t2_w_default = 0
        biomass_t2_wo_default = 0

        combustion_factor_t2_start_default = 0
        combustion_factor_t2_w_default = 0
        combustion_factor_t2_wo_default = 0

        filled_scenarios = serializers.get_filled_scenarios(self.input.__dict__, ["grassland_management_type"])

        if utils.ScenarioTypes.START.value in filled_scenarios:
            try:
                soc_t2_start_default = ipcc.GrasslandSOC.objects.get(grassland_management_type=self.input.grassland_management_type_start).value
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise ValueError(f"Grassland default SOC start value not found for climate {self.climate} and management type {self.input.grassland_management_type_start}")

        if utils.ScenarioTypes.WITH.value in filled_scenarios:
            try:
                soc_t2_w_default = ipcc.GrasslandSOC.objects.get(grassland_management_type=self.input.grassland_management_type_w).value
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise ValueError(f"Grassland default SOC with value not found for climate {self.climate} and management type {self.input.grassland_management_type_w}")

        if utils.ScenarioTypes.WITHOUT.value in filled_scenarios:
            try:
                soc_t2_wo_default = ipcc.GrasslandSOC.objects.get(grassland_management_type=self.input.grassland_management_type_wo).value
            except ipcc.GrasslandStockExchangeFactor.DoesNotExist:
                raise ValueError(f"Grassland default SOC without value not found for climate {self.climate} and management type {self.input.grassland_management_type_wo}")

        try:
            agb = ipcc.GrasslandAGB.objects.get(climate=self.climate, moisture=self.moisture).value
        except ipcc.GrasslandAGB.DoesNotExist:
            raise ValueError(f"Grassland default AGB value not found for climate {self.climate} and moisture {self.moisture}")

        try:
            cf = api.GrasslandParameter.objects.get(name="default_combustion_factor").value
        except api.GrasslandParameter.DoesNotExist:
            raise ValueError("Grassland default combustion factor not found.")

        biomass_t2_start_default = agb
        biomass_t2_w_default = agb
        biomass_t2_wo_default = agb

        combustion_factor_t2_start_default = cf
        combustion_factor_t2_w_default = cf
        combustion_factor_t2_wo_default = cf

        return SimpleNamespace(
            soc_t2_start_default=soc_t2_start_default,
            soc_t2_w_default=soc_t2_w_default,
            soc_t2_wo_default=soc_t2_wo_default,
            biomass_t2_start_default=biomass_t2_start_default,
            biomass_t2_w_default=biomass_t2_w_default,
            biomass_t2_wo_default=biomass_t2_wo_default,
            combustion_factor_t2_start_default=combustion_factor_t2_start_default,
            combustion_factor_t2_w_default=combustion_factor_t2_w_default,
            combustion_factor_t2_wo_default=combustion_factor_t2_wo_default,
        )


class AnnualCroppingDefaults(Defaults):
    pass

    def get_defaults(self) -> dict:
        self.input: api.AnnualCropping

        soc_t2_start_default = 0
        soc_t2_w_default = 0
        soc_t2_wo_default = 0

        fi_t2_start_default = 0
        fi_t2_w_default = 0
        fi_t2_wo_default = 0

        fmg_t2_start_default = 0
        fmg_t2_w_default = 0
        fmg_t2_wo_default = 0

        flu_t2_start_default = 0
        flu_t2_w_default = 0
        flu_t2_wo_default = 0

        burning_emission_factor_t2_start_default = 0
        burning_emission_factor_t2_w_default = 0
        burning_emission_factor_t2_wo_default = 0

        defaults = calcs.AnnualCropCalculator(self.input)
        defaults.get_defaults()

        soc_t2_start_default = defaults.soc.value
        soc_t2_w_default = defaults.soc.value
        soc_t2_wo_default = defaults.soc.value

        fi_t2_start_default = defaults.fi_start.value
        fi_t2_w_default = defaults.fi_w.value
        fi_t2_wo_default = defaults.fi_wo.value

        fmg_t2_start_default = defaults.fmg_start.value
        fmg_t2_w_default = defaults.fmg_w.value
        fmg_t2_wo_default = defaults.fmg_wo.value

        flu_t2_start_default = defaults.flu_start.value
        flu_t2_w_default = defaults.flu_w.value
        flu_t2_wo_default = defaults.flu_wo.value

        burning_emission_factor_t2_start_default = defaults.fires_start.value
        burning_emission_factor_t2_w_default = defaults.fires_w.value
        burning_emission_factor_t2_wo_default = defaults.fires_wo.value

        # # TODO: Move this to staticmethod of calculators, maybe?
        # try:
        #     soc = ipcc.SoilOrganicCarbon.objects.get(climate=self.climate, moisture=self.moisture, soil_type=self.soil_type).value
        # except ipcc.SoilOrganicCarbon.DoesNotExist:
        #     raise ValueError(f"Soil organic carbon default value not found for climate {self.climate}, moisture {self.moisture} and soil type {self.soil_type}")

        # try:
        #     fi_t2_start_default = calcs.get_fi_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        # except ipcc.FIData.DoesNotExist:
        #     raise ValueError("Annual cropping default FI start value not found.")

        # try:
        #     fi_t2_w_default = calcs.get_fi_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        # except ipcc.FIData.DoesNotExist:
        #     raise ValueError("Annual cropping default FI with value not found.")

        # try:
        #     fi_t2_wo_default = calcs.get_fi_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
        # except ipcc.FIData.DoesNotExist:
        #     raise ValueError("Annual cropping default FI without value not found.")

        # try:
        #     fmg_t2_start_default = calcs.get_fmg_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        # except ipcc.FMGData.DoesNotExist:
        #     raise ValueError("Annual cropping default FMG start value not found.")

        # try:
        #     fmg_t2_w_default = calcs.get_fmg_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        # except ipcc.FMGData.DoesNotExist:
        #     raise ValueError("Annual cropping default FMG with value not found.")

        # try:
        #     fmg_t2_wo_default = calcs.get_fmg_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
        # except ipcc.FMGData.DoesNotExist:
        #     raise ValueError("Annual cropping default FMG without value not found.")

        # try:
        #     flu_t2_start_default = calcs.get_flu_data(self.module_start, self.climate, self.moisture, utils.ScenarioTypes.START)
        # except ipcc.FLUData.DoesNotExist:
        #     raise ValueError("Annual cropping default FLU start value not found.")

        # try:
        #     flu_t2_w_default = calcs.get_flu_data(self.module_w, self.climate, self.moisture, utils.ScenarioTypes.WITH)
        # except ipcc.FLUData.DoesNotExist:
        #     raise ValueError("Annual cropping default FLU with value not found.")

        # try:
        #     flu_t2_wo_default = calcs.get_flu_data(self.module_wo, self.climate, self.moisture, utils.ScenarioTypes.WITHOUT)
        # except ipcc.FLUData.DoesNotExist:
        #     raise ValueError("Annual cropping default FLU without value not found.")

        # try:
        #     burning_emission_factor = ipcc.FiresCombustionFactor.objects.get(land_use_type=self.input.land_use_type_start).value
        # except ipcc.FiresCombustionFactor.DoesNotExist:
        #     raise ValueError(f"Annual cropping default burning emission factor not found for land use type {self.input.land_use_type_start}")

        # soc_t2_start_default = soc
        # soc_t2_w_default = soc
        # soc_t2_wo_default = soc

        # burning_emission_factor_t2_start_default = burning_emission_factor
        # burning_emission_factor_t2_w_default = burning_emission_factor
        # burning_emission_factor_t2_wo_default = burning_emission_factor

        # return SimpleNamespace(
        #     soc_t2_start_default=soc_t2_start_default,
        #     soc_t2_w_default=soc_t2_w_default,
        #     soc_t2_wo_default=soc_t2_wo_default,
        #     fi_t2_start_default=fi_t2_start_default,
        #     fi_t2_w_default=fi_t2_w_default,
        #     fi_t2_wo_default=fi_t2_wo_default,
        #     fmg_t2_start_default=fmg_t2_start_default,
        #     fmg_t2_w_default=fmg_t2_w_default,
        #     fmg_t2_wo_default=fmg_t2_wo_default,
        #     flu_t2_start_default=flu_t2_start_default,
        #     flu_t2_w_default=flu_t2_w_default,
        #     flu_t2_wo_default=flu_t2_wo_default,
        #     burning_emission_factor_t2_start_default=burning_emission_factor_t2_start_default,
        #     burning_emission_factor_t2_w_default=burning_emission_factor_t2_w_default,
        #     burning_emission_factor_t2_wo_default=burning_emission_factor_t2_wo_default,
        # )

        return SimpleNamespace(
            soc_t2_start_default=soc_t2_start_default,
            soc_t2_w_default=soc_t2_w_default,
            soc_t2_wo_default=soc_t2_wo_default,
            fi_t2_start_default=fi_t2_start_default,
            fi_t2_w_default=fi_t2_w_default,
            fi_t2_wo_default=fi_t2_wo_default,
            fmg_t2_start_default=fmg_t2_start_default,
            fmg_t2_w_default=fmg_t2_w_default,
            fmg_t2_wo_default=fmg_t2_wo_default,
            flu_t2_start_default=flu_t2_start_default,
            flu_t2_w_default=flu_t2_w_default,
            flu_t2_wo_default=flu_t2_wo_default,
            burning_emission_factor_t2_start_default=burning_emission_factor_t2_start_default,
            burning_emission_factor_t2_w_default=burning_emission_factor_t2_w_default,
            burning_emission_factor_t2_wo_default=burning_emission_factor_t2_wo_default,
        )
