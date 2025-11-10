from .ghg_emissions_classes import Emission, ActivityTypes
from typing import List


class InventoryPerGasperActivity(Emission):
    def __init__(self, gas_type, emission, activity):
        super.init(emission, gas_type)
        self.activity: ActivityTypes = activity

    def to_dict(self):
        return {"activity": self.activity.value, **super().to_dict()}


class Inventory:
    def __init__(self):
        self.emission_by_sector_by_gas: List[InventoryPerGasperActivity] = []

    def to_dict(self):
        return [inventory.to_dict() for inventory in self.emission_by_sector_by_gas]
