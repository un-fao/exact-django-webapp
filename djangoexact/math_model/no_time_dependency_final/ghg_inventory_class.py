import copy
from .ghg_emissions_classes import Emission, ActivityTypes, GasTypes, BreakdownTypes
from collections import defaultdict


def _check_value(gas_type, value, activity):
    """An inventory row is a single baseline (start-year) number.

    Producers have twice put something else in this slot -- a per-year series, and a
    GasTypes enum from swapped positional args -- and neither failed until
    Inventory.to_total() summed it three frames later, or never at all, since
    to_by_activity_gas passes the value straight into the response and cache JSON.
    Fail at the producer instead. Every value entering an Inventory passes here.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Inventory value for {gas_type} / {activity} must be a number, got {type(value).__name__}: {value!r}")


class InventoryPerGasPerActivity(Emission):
    def __init__(self, gas_type: GasTypes, value: float, activity: ActivityTypes):
        _check_value(gas_type, value, activity)
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
        _check_value(gas_type, value, activity)  # the merge branch below never reaches the constructor
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
