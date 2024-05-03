import copy
import re
import uuid
from enum import Enum

from django.apps import apps
from django.db import models
from rest_framework import exceptions, status
from rest_framework.response import Response

import api.models as api_models

CN_RATIO_CROP = 10
CN_RATIO_GRASSLAND = 15
MANGROVE_FACTOR = 0.451
NON_MANGROVE_FACTOR = 0.47
MANGROVES = "Mangroves"
DATA = "data"
RESULTS = "results"
DETAILS = "details"
API = "api"
TROPHIC_STATE = 0.7
INCLUDE_RELATED = "include_related"


class ManureManagementTypes(Enum):
    PRP = "Pasture/Range/Paddock"


class ScenarioTypes(Enum):
    START = "start"
    WITH = "w"
    WITHOUT = "wo"


class EmissionTypes(Enum):
    CO2 = "CO2"
    CH4 = "CH4"
    N2O = "N2O"
    N2O_VOLATILIZATION = "N2O Volatilization"
    N2O_LEACHING = "N2O Leaching"


def avg(lst):
    return sum(lst) / len(lst)


def snake_case(str):
    res = [str[0].lower()]
    for c in str[1:]:
        if c in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            res.append("_")
            res.append(c.lower())
        else:
            res.append(c)

    return "".join(res)


def sanitize_for_model(str: str):
    return str.replace(" ", "").replace("-", "").replace("_", "")


def error(msg):
    return {DETAILS: msg}


def get_model(name, app_name="api", suffix="Input"):
    return apps.get_model(app_name, sanitize_for_model(name + suffix))


def get_query_param_or_validation_error(request, param_name):
    param = request.query_params.get(param_name)
    if param is None:
        raise exceptions.ValidationError(f"{param_name} is required")
    return param


def get_url_name(model_name):
    url_name = model_name

    # regex split on non consecutive capital letters
    url_name = "".join([f"-{x}" for x in re.split(r"(?<!^)(?=[A-Z](?![A-Z]|$))", url_name)]).lower()
    url_name = url_name[1:]

    if url_name[-1] == "s":
        url_name += "es"
    else:
        url_name += "s"
    return url_name


# define ErrorResponse class
class ErrorResponse(Response):
    def __init__(self, data, status=status.HTTP_400_BAD_REQUEST):
        super().__init__(error(data), status=status)


def is_start_with_changed(_class: object, luc):
    return luc.module_type_start.class_name == _class.__name__ and luc.module_type_start != luc.module_type_wo


def get_thread_attributes(module: models.Model):
    return [attr for attr in module._meta.get_fields() if attr.name.endswith("_thread")]


def get_module_status(self, activity, module_type):
    module_attr = getattr(activity, module_type.class_name.lower(), None)
    module = module_attr.first() if module_attr else None
    return module.status if module else None


def has_project_permission(permission, user, project):
    """
    Check if a user has a specific permission for a project.

    Args:
        permission (str): The codename of the permission to check, without the app name.
        user (User): The user object.
        project (Project): The project object.

    Returns:
        bool: True if the user has the permission, False otherwise.
    """
    membership: models.UserProjectGroup = project.members.filter(user=user).first()
    can_access = membership and membership.group.permissions.filter(codename=permission).exists()

    return can_access


def find_modules(activity):
    """
    Find all modules in a project.

    Args:
        project (Project): The project object.

    Returns:
        list: A list of all modules in the project.
    """
    modules = []
    for module_type in activity.module_types.all():
        module_attr = getattr(activity, module_type.class_name.lower(), None)
        module = module_attr.first() if module_attr else None
        if module:
            modules.append(module)

    return modules


def copy_project(project):
    project_copy = copy.deepcopy(project)
    project_copy.pk = None
    project_copy.name = f"{project_copy.name} copy {uuid.uuid4().hex[:6]}"
    project_copy._state.adding = True
    project_copy.save()

    for activity in project.activities.all():
        copy_activity(activity, project_copy)

    return project_copy


def copy_activity(activity, new_project=None):
    activity_copy = copy.deepcopy(activity)
    activity_copy.pk = None
    activity_copy.name = f"{activity_copy.name} copy {uuid.uuid4().hex[:6]}"
    if new_project:
        activity_copy.project = new_project
    activity_copy._state.adding = True
    activity_copy.save()

    activity_copy.module_types.add(*activity.module_types.all())
    activity_copy.save()

    luc_copy = None

    for module in find_modules(activity):
        module_copy = copy.deepcopy(module)
        module_copy.pk = None
        module_copy.activity = activity_copy
        module_copy._state.adding = True
        module_copy.land_use_change = None
        module_copy.save()

        has_luc = getattr(module, "land_use_change", None)

        if has_luc:
            if not luc_copy:
                luc_copy = copy.deepcopy(module.land_use_change)
                luc_copy.pk = None
                luc_copy.activity = activity_copy
                luc_copy._state.adding = True
                luc_copy.save()

            module_copy.land_use_change = luc_copy
            module_copy.save()

        submodules = None

        if module.__class__.__name__ == "FloodedRice":
            submodules = module.minor_seasons.all()
        elif module.__class__.__name__ == "Input":
            submodules = module.input_entries.all()
        elif module.__class__.__name__ == "Energy":
            submodules = module.electricities.all()
            submodules.extend(module.fuels.all())
        elif module.__class__.__name__ == "Irrigaition":
            submodules = module.irrigation_systems.all()
            submodules.extend(module.irrigation_phases.all())

        if submodules:
            for submodule in submodules:
                submodule.pk = None
                submodule.parent = module_copy
                submodule._state.adding = True
                submodule.save()

    return activity


def create_module_threads(module_instance):
    for attr in dir(module_instance):
        if attr.endswith("_thread") and getattr(module_instance, attr, None) is None:
            setattr(module_instance, attr, api_models.CommentThread.objects.create())
    module_instance.save()


def getany(objects: list[object], key: str):
    """
    Returns the value of the specified key from the first object in the arguments list that has the key attribute.

    Args:
        *args (list[object]): The list of objects to search for the key attribute.
        key (str): The name of the key attribute to retrieve.

    Returns:
        object: The value of the specified key from the first object that has the key attribute, or None if no object has the key attribute.

    Raises:
        ValueError: If any argument in the args list is not an object.
    """
    if not all([isinstance(obj, object) for obj in objects]):
        raise ValueError("All arguments must be objects")

    for obj in objects:

        obj_type = type(obj)

        if obj_type is dict:
            if key in obj:
                return obj[key]
        else:
            if hasattr(obj, key):
                return getattr(obj, key)
    return None


def getattr_or_default(obj, key, default=0):
    """
    Returns the value of the specified key from the object, or 0 if the object does not have the key attribute.

    Args:
        obj (object): The object to retrieve the key attribute from.
        key (str): The name of the key attribute to retrieve.

    Returns:
        object: The value of the specified key from the object, or 0 if the object does not have the key attribute.
    """
    _attr = getattr(obj, key, 0)
    return _attr if _attr else default
