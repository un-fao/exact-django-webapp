from types import SimpleNamespace

import ipcc.models as ipcc

import api.models as api
import api.serializers as serializers
import api.utilities as utils


# Create a base class that all other classes inherit from
class Defaults:
    def __init__(self, input: api.Module):
        self.input = input
        self.activity = input.parent.activity if input.parent else input.activity
        self.climate: api.Climate = self.activity.climate_t2 if self.activity.climate_t2 else self.activity.project.climate
        self.moisture: api.Moisture = self.activity.moisture_t2 if self.activity.moisture_t2 else self.activity.project.moisture

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
        else:
            try:
                getattr(api, input.__class__.__name__)
            except AttributeError:
                raise ValueError("Invalid module type.")

            raise NotImplementedError(f"Defaults for {input.__class__.__name__} have not been implemented.")


class GrasslandDefaults(Defaults):

    def __init__(self, input: api.Grassland):
        super().__init__(input)

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
