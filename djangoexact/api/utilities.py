import copy
import re
import uuid
from enum import Enum

from django.apps import apps
from django.db import models
from rest_framework import exceptions, status
from rest_framework.response import Response
from simple_history.models import HistoricalRecords
from simple_history.utils import update_change_reason

import api.models as api_models

import logging as log

CN_RATIO_CROP = 10
CN_RATIO_GRASSLAND = 15
MANGROVE_FACTOR = 0.451
NON_MANGROVE_FACTOR = 0.47
PAVED_SETTLEMENT_SOC_MULTIPLIER = 0.8
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


class ChangeReasons(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class InvitationStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


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
    full_name = name
    if suffix:
        full_name += suffix
    return apps.get_model(app_name, sanitize_for_model(full_name))


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

    if user.is_superuser:
        return True

    memberships: list[api_models.ProjectMembership] = project.members.filter(user=user)

    can_access = memberships and any([membership.group.permissions.filter(codename=permission).exists() for membership in memberships])

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
    organic_soil_copy = None

    for module in find_modules(activity):
        if module.__class__.__name__ == "LandUseChange" or module.__class__.__name__ == "OrganicSoil":
            continue

        module_copy = copy.deepcopy(module)
        module_copy.pk = None
        module_copy.activity = activity_copy
        module_copy._state.adding = True
        module_copy.land_use_change = None
        module_copy.organic_soil = None
        module_copy.save()

        has_luc = getattr(module, "land_use_change", None)
        has_organic_soil = getattr(module, "organic_soil", None)

        if has_luc:
            if not luc_copy:
                luc_copy = copy.deepcopy(module.land_use_change)
                luc_copy.pk = None
                luc_copy.activity = activity_copy
                luc_copy._state.adding = True
                luc_copy.save()

            module_copy.land_use_change = luc_copy
            module_copy.save()

        if has_organic_soil:
            if not organic_soil_copy:
                organic_soil_copy = copy.deepcopy(module.organic_soil)
                organic_soil_copy.pk = None
                organic_soil_copy.activity = activity_copy
                organic_soil_copy._state.adding = True
                organic_soil_copy.save()

            module_copy.organic_soil = organic_soil_copy
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


def create_comment_threads(module_instance):
    for attr in dir(module_instance):
        if attr.endswith("_thread") and getattr(module_instance, attr, None) is None:
            setattr(module_instance, attr, api_models.CommentThread.objects.create())
    module_instance.save()
    update_change_reason(module_instance, "update")


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


def get_or_raise(model, filter_criteria, error_message, method="get") -> models.QuerySet | models.Model:
    """
    Retrieves a single instance of the given model that matches the filter criteria,
    or raises an exception with the specified error message if no instance is found.

    Args:
        model (django.db.models.Model): The model class to query.
        filter_criteria (dict): The filter criteria to apply when querying the model.
        error_message (str): The error message to raise if no instance is found.
        method (str, optional): The method to use for querying the model. Defaults to "get".

    Returns:
        django.db.models.Model: The retrieved instance.

    Raises:
        Exception: If no instance is found and the input status name is "READY".
    """
    try:
        attr = getattr(model.objects, method)
        if not callable(attr):
            raise AttributeError(f"Method '{method}' is not callable on {model.__name__} objects.")
        return attr(**filter_criteria)
    except model.DoesNotExist:
        raise Exception(error_message)


def update_activity_status_and_completion(activity):
    """
    Updates the status of the activity based on the status of its modules.

    Args:
        activity (Activity): The activity object to update.
    """
    statuses = [module.status for module in find_modules(activity)]

    ready_count = statuses.count(api_models.StatusType.objects.get(name="READY"))
    percentage_complete = ready_count / len(statuses)

    if percentage_complete == 1:
        activity.status = api_models.StatusType.objects.get(name="READY")
    elif percentage_complete > 0:
        activity.status = api_models.StatusType.objects.get(name="IN PROGRESS")
    else:
        activity.status = api_models.StatusType.objects.get(name="EMPTY")

    activity.completion_percentage = percentage_complete
    activity.save()

    return activity.status


# NOTE: This could be done with signals, but I saw there are no signals as of now
# so I kept this approach for consistency. Can be changed later if needed.
def get_activity_default_status():
    return api_models.StatusType.objects.get_or_create(name="EMPTY")[0]


def get_default_peat_type():
    return api_models.PeatType.objects.get_or_create(name="Nutrient Poor")[0]


def find_organic_soil_parent_module(organic_soil) -> tuple:
    """
    Find the parent module of the Organic Soil module.

    Args:
        organic_soil: The Organic Soil module.

    Returns:
        A tuple containing the parent module [api.models.LandModule] and its module type [api.models.ModuleType]

    Raises:
        ValueError: If the parent module or module type cannot be found.
    """

    # NOTE: This is always true as long as Organic Soil is a OneToOneField of LandModule
    parent_module: api_models.LandModule = next(attr for attr in dir(organic_soil) if attr.startswith("organic_soil_") and (attr not in ["organicsoil"] and isinstance(getattr(organic_soil, attr, None), api_models.LandModule)))

    if not parent_module:
        raise ValueError(f"Could not find parent module for Organic Soil")

    parent_module_name = parent_module.split("_")[-1]
    parent_module_type: api_models.ModuleType = api_models.ModuleType.objects.filter(class_name__iexact=parent_module_name).first()

    if not parent_module_type:
        raise ValueError(f"Could not find module type for {parent_module_name}")

    ParentModule = apps.get_model(app_label="api", model_name=parent_module_type.class_name)
    parent_module = ParentModule.objects.get(organic_soil=organic_soil)

    return parent_module, parent_module_type


def get_changes(records: list[HistoricalRecords]):

    class ChangeLog:
        def __init__(self, date, user, reason, changes):
            self.date = date
            self.user = user
            self.reason = reason
            self.changes: list[Change] = changes

    class Change:
        def __init__(self, field, old, new):
            self.field = field
            self.old = old
            self.new = new

    changes = []
    for record in records:
        if record.prev_record is None:
            changes.append(ChangeLog(record.history_date, record.history_user.email, ChangeReasons.CREATE.value, []))
            continue

        if record.next_record is None:
            continue

        delta = record.diff_against(record.prev_record)
        change_log: ChangeLog = ChangeLog(record.history_date, record.history_user.email, record.history_change_reason, [])
        for change in delta.changes:
            change_log.changes.append(Change(change.field, change.old, change.new))

        if len(change_log.changes) > 0:
            changes.append(change_log)

    return changes


def get_modules(activity, serialized=True) -> list:
    modules = []
    module_serializers_list = []
    for module in activity.module_types.all():
        try:
            module_model = apps.get_model(API, module.class_name)
        except LookupError:
            log.warning(f"get_modules: Module {module.name} not found")
            continue
        module_object = module_model.objects.filter(activity__id=activity.pk).first()
        if module_object:
            modules.append(module_object)
            from api.serializers import get_module_serializer

            module_dict = get_module_serializer(module_model)(module_object).data
            module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules
