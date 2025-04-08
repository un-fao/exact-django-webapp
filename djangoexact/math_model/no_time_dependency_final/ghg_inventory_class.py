
from .ghg_emissions_classes import Emission, ActivityTypes
from typing import List

class InventoryPerGasperActivity(Emission):
    def __init__(self, gas_type, emission, activity):
        super.init(gas_type,emission)
        self.activity: ActivityTypes = activity  

class Inventory:
    def __init__(self,):
        self.emission_by_sector_by_gas: List[InventoryPerGasperActivity] = []