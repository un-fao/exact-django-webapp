import copy
from .ghg_emissions_classes import Emission, ActivityTypes, GasTypes, BreakdownTypes
from typing import List
from collections import defaultdict


class InventoryPerGasPerActivity(Emission):
    def __init__(self, gas_type: GasTypes, value: float, activity: ActivityTypes):
        super().__init__(value, gas_type)
        self.activity: ActivityTypes = activity

    def to_dict(self):
        return {
            "activity": self.activity.value if self.activity else None,
            "gas_type": {"name": self.gas_type.name if self.gas_type else None},
            "value": self.value,
        }

    def __add__(self, other):
        return InventoryPerGasPerActivity(self.gas_type, self.value + other.value, self.activity)

    def __sub__(self, other):
        return InventoryPerGasPerActivity(self.gas_type, self.value - other.value, self.activity)


class _InventoryList(list):
    """List subclass that can also be called as a function for backward compatibility."""

    def __call__(self, item):
        self.append(item)


class Inventory:
    def __init__(self):
        self.emissions_by_sector_by_gas = _InventoryList()

    def __deepcopy__(self, memo):
        new_obj = Inventory.__new__(Inventory)
        new_obj.emissions_by_sector_by_gas = _InventoryList(copy.deepcopy(item, memo) for item in self.emissions_by_sector_by_gas)
        return new_obj

    def to_dict(self):
        return [item.to_dict() for item in self.emissions_by_sector_by_gas]

    def to_total(self):
        return sum(item.value for item in self.emissions_by_sector_by_gas)

    def to_by_activity(self):
        aggregated = defaultdict(float)
        for item in self.emissions_by_sector_by_gas:
            activity_key = item.activity.value if item.activity else None
            aggregated[activity_key] += item.value
        return [{"activity": k, "value": v} for k, v in aggregated.items()]

    def to_by_gas(self):
        aggregated = defaultdict(float)
        for item in self.emissions_by_sector_by_gas:
            gas_key = item.gas_type.name if item.gas_type else None
            aggregated[gas_key] += item.value
        return [{"gas_type": {"name": k}, "value": v} for k, v in aggregated.items()]

    def to_by_activity_gas(self):
        return self.to_dict()

    def breakdown(self, by=BreakdownTypes.TOTAL):
        match by:
            case BreakdownTypes.TOTAL:
                return self.to_total()
            case BreakdownTypes.ACTIVITY:
                return self.to_by_activity()
            case BreakdownTypes.GAS:
                return self.to_by_gas()
            case BreakdownTypes.ACTIVITY_GAS:
                return self.to_by_activity_gas()
            case _:
                return self.to_total()

    def add_emission(self, gas_type: GasTypes, value: float, activity: ActivityTypes):
        for item in self.emissions_by_sector_by_gas:
            if item.gas_type == gas_type and item.activity == activity:
                item.value += value
                return
        self.emissions_by_sector_by_gas.append(InventoryPerGasPerActivity(gas_type, value, activity))

    def __add__(self, other):
        result = copy.deepcopy(self)
        for item in other.emissions_by_sector_by_gas:
            result.add_emission(item.gas_type, item.value, item.activity)
        return result

    def __sub__(self, other):
        result = copy.deepcopy(self)
        for item in other.emissions_by_sector_by_gas:
            result.add_emission(item.gas_type, -item.value, item.activity)
        return result


class InventoryResult:
    def __init__(self, w: Inventory, wo: Inventory, balance: Inventory = None):
        self.total_w = w
        self.total_wo = wo
        self.balance = copy.deepcopy(w) - copy.deepcopy(wo) if balance is None else copy.deepcopy(balance)

    def to_dict(self, by=BreakdownTypes.TOTAL):
        return {
            "total_w": self.total_w.breakdown(by),
            "total_wo": self.total_wo.breakdown(by),
            "balance": self.balance.breakdown(by),
        }

    def add(self, result):
        if not isinstance(result, self.__class__):
            raise TypeError(f"Cannot add {type(result)} to {type(self)}.")
        self.total_w = self.total_w + result.total_w
        self.total_wo = self.total_wo + result.total_wo
        self.balance = self.total_w - self.total_wo
        return self

    def __add__(self, other):
        return self.add(other)
