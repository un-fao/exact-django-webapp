import copy
import re
import uuid
from enum import Enum

from django.apps import apps
from django.db import models
from rest_framework import exceptions, status
from rest_framework.response import Response
from simple_history.models import HistoricalRecords
from django.utils.translation import get_language
from django.core.exceptions import FieldDoesNotExist
from django.core.mail import send_mail
import os
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import api.models as api_models
import ipcc.models as ipcc_models
from datetime import timedelta

import logging as log
from django.utils.translation import gettext_lazy as _
from dataclasses import dataclass
from django.db import transaction
import api.security as security

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

FOSSIL_METHANE_FUELS = ["peat", "charcoal"]
ELECTRIC_FUEL_TYPES = ["electricity", "renewable"]


class ManureManagementTypes(Enum):
    PRP = "Pasture/Range/Paddock"


class ScenarioTypes(Enum):
    START = "start", "start"
    WITH = "w", "with"
    WITHOUT = "wo", "without"

    def __new__(cls, value, verbose_name):
        # Retain the original behavior for value
        obj = object.__new__(cls)
        obj._value_ = value
        # Set additional attributes
        obj.verbose_name = verbose_name
        return obj


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


def snake_case_to_readable(str):
    return " ".join(str.split("_")).title()


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

    can_access = False

    if memberships:
        for membership in memberships:
            if membership.group.permissions.filter(codename=permission).exists():
                can_access = True
                break

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


@transaction.atomic
def get_unique_name(instance, name):
    """
    Generates a unique name for a Django model instance by appending a counter if necessary.

    This function checks if the provided name already exists for the given model class.
    If the name is already taken, it appends a counter in parentheses (e.g., "name (1)")
    and increments the counter until a unique name is found.

    Args:
        instance: A Django model instance to check uniqueness against.
        name (str): The original name to use or modify.

    Returns:
        str: A unique name - either the original name if it's unique, or the name with
             a counter in parentheses appended (e.g., "name (1)", "name (2)", etc.).
    """

    if not instance.__class__.objects.filter(name=name).exists():
        return name

    i = 1
    while instance.__class__.objects.filter(name=f"{name} ({i})").exists():
        i += 1

    return f"{name} ({i})"


def _ensure_admin_membership(project_copy, owner):
    """Grant `owner` an Admin membership on `project_copy` if they don't already have one.

    Checks membership against project_copy (the TARGET/new project), not the source
    project being copied from. Checking the source was the original bug: it let a copy
    without a membership on the new project pass silently whenever the owner already
    happened to be an Admin on the source.
    """
    if not project_copy.members.filter(user=owner, group__name="Admin").exists():
        api_models.ProjectMembership.objects.create(
            user=owner,
            project=project_copy,
            group=api_models.Group.objects.get(name="Admin"),
        )


@transaction.atomic
def create_project_shell(project, owner):
    """Clone the Project row only (fast). Activities are copied separately via copy_activities_into."""
    project_copy = copy.deepcopy(project)
    project_copy.pk = None
    project_copy.name = get_unique_name(project_copy, project_copy.name)
    project_copy._state.adding = True
    project_copy.is_finalized = False
    project_copy.is_public = False
    project_copy.owner = owner
    project_copy.save()

    _ensure_admin_membership(project_copy, owner)

    return project_copy


def copy_activities_into(source_project, target_project, owner):
    """Deep-copy every activity of source_project into target_project."""
    for activity in source_project.activities.all():
        copy_activity(activity, target_project, owner)


@transaction.atomic
def copy_project(project, owner):
    try:
        project_copy = create_project_shell(project, owner)
        copy_activities_into(project, project_copy, owner)
        return project_copy
    except Exception as e:
        log.error(f"Error copying project: {e}")
        raise e


@transaction.atomic
def copy_threads(module_from: "api_models.Module", module_to: "api_models.Module"):
    """
    Copy the threads of a module and return the copied threads.

    Args:
        module: The module whose threads to copy.

    Returns:
        list[api_models.CommentThread]: The list of copied threads.
    """

    copied_threads = []

    # Iterate through all fields of the module to find thread fields
    for field in module_to._meta.get_fields():
        if field.name.endswith("_thread") and hasattr(field, "related_model"):
            if field.related_model == api_models.CommentThread:
                thread_instance = getattr(module_from, field.name, None)

                if thread_instance is None:
                    continue

                # Create a new thread copy
                thread_copy = copy.deepcopy(thread_instance)
                thread_copy.pk = None
                thread_copy._state.adding = True
                thread_copy.save()

                # Copy all comments from the original thread
                for comment in thread_instance.comments.all():
                    comment_copy = copy.deepcopy(comment)
                    comment_copy.pk = None
                    comment_copy.thread = thread_copy
                    comment_copy._state.adding = True
                    comment_copy.save()

                # Assign the new thread to the module
                setattr(module_to, field.name, thread_copy)
                copied_threads.append(thread_copy)

    return copied_threads


@transaction.atomic
def clear_threads(module):
    """
    Clear the threads of a module by deleting all associated CommentThread instances.

    Args:
        module: The module whose threads to clear.
    """

    # Iterate through all fields of the module to find thread fields
    for field in module._meta.get_fields():
        if field.name.endswith("_thread") and hasattr(field, "related_model"):
            if field.related_model == api_models.CommentThread:
                thread_instance = getattr(module, field.name, None)
                if thread_instance is not None:
                    setattr(module, field.name, None)


@transaction.atomic
def handle_threads(module_from: "api_models.Module", module_to: "api_models.Module", owner=None):
    """
    Handle the copying of threads from one module to another, ensuring that the threads are copied correctly
    and that the new module has the correct ownership.

    Args:
        module_from: The source module from which to copy threads.
        module_to: The destination module to which threads will be copied.
        owner: The owner of the new module, if applicable.

    Returns:
        None
    """

    activity = module_from.activity

    # check_permission returns None when the user HAS the permission and an
    # ErrorResponse when they do not, so its result must be compared against
    # None rather than used as a truthiness test. The codename was also wrong:
    # "can_view_comment" is declared nowhere in the project, so the lookup always
    # failed for non-superusers and logged an error for every module copied.
    permission_error = security.check_permission("view_comment", owner, activity.project)
    if owner is not None and permission_error is None:
        copy_threads(module_from, module_to)
    else:
        clear_threads(module_to)


@transaction.atomic
def copy_activity(activity: "api_models.Activity", new_project=None, owner=None):
    activity_copy = copy.deepcopy(activity)
    activity_copy.pk = None
    activity_copy.name = get_unique_name(activity_copy, activity_copy.name)
    if new_project:
        activity_copy.project = new_project
    activity_copy._state.adding = True
    activity_copy.save()

    activity_copy.module_types.add(*activity.module_types.all())
    activity_copy.save()

    luc_copy = None
    organic_soil_copy = None

    luc = list(filter(lambda x: x.__class__.__name__ == "LandUseChange", activity.modules))[0] if list(filter(lambda x: x.__class__.__name__ == "LandUseChange", activity.modules)) else None
    organic_soil = list(filter(lambda x: x.__class__.__name__ == "OrganicSoil", activity.modules))[0] if list(filter(lambda x: x.__class__.__name__ == "OrganicSoil", activity.modules)) else None

    if luc:
        luc_copy = copy.deepcopy(luc)
        luc_copy.pk = None
        luc_copy.activity = activity_copy
        luc_copy._state.adding = True
        luc_copy.organic_soil = None
        handle_threads(luc, luc_copy, owner)
        luc_copy.save()

    if organic_soil:
        organic_soil_copy = copy.deepcopy(organic_soil)
        organic_soil_copy.pk = None
        organic_soil_copy.activity = activity_copy
        organic_soil_copy._state.adding = True
        if luc_copy:
            organic_soil_copy.land_use_change = luc_copy
        handle_threads(organic_soil, organic_soil_copy, owner)
        organic_soil_copy.save()

    for module in list(filter(lambda x: x.__class__.__name__ not in ["LandUseChange", "OrganicSoil"], activity.modules)):
        module: api_models.Module
        module_copy = copy.deepcopy(module)
        module_copy.pk = None
        module_copy.activity = activity_copy
        module_copy.land_use_change = None
        module_copy._state.adding = True
        if luc_copy:
            module_copy.land_use_change = luc_copy
        elif organic_soil_copy:
            module_copy.organic_soil = organic_soil_copy
        handle_threads(module, module_copy, owner)
        module_copy.save()

        submodules = module.submodules if hasattr(module, "submodules") else []

        if submodules:
            for submodule in submodules:
                submodule.pk = None
                submodule.parent = module_copy
                submodule._state.adding = True
                handle_threads(submodule, submodule, owner)
                submodule.save()

    return activity_copy


def create_comment_threads(module_instance):
    for attr in dir(module_instance):
        if attr.endswith("_thread") and getattr(module_instance, attr, None) is None:
            setattr(module_instance, attr, api_models.CommentThread.objects.create())
    if not module_instance._state.adding:
        if module_instance.history.exists():
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

        if obj_type is dict or obj_type.__name__ == "OrderedDict":
            if key in obj:
                return obj[key]
        else:
            if hasattr(obj, key) and getattr(obj, key) is not None:
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


def get_soc(module, climate, moisture, soil_type, scenario: ScenarioTypes) -> models.QuerySet | models.Model:
    if hasattr(module, f"soc_t2_{scenario.value}"):
        return getattr(module, f"soc_t2_{scenario.value}")

    filter_criteria = {"climate": climate, "moisture": moisture, "soil_type": soil_type}
    return get_or_raise(ipcc_models.SoilOrganicCarbon, filter_criteria, f"Could not find SOC for {module.__class__.__name__}). Please insert time 2 SOC values.")


def update_activity_status_and_completion(activity):
    """
    Updates the status of the activity based on the status of its modules.

    Args:
        activity (Activity): The activity object to update.
    """
    statuses = [module.status for module in find_modules(activity)]

    ready_count = statuses.count(api_models.StatusType.objects.get(name_en="READY"))
    percentage_complete = ready_count / len(statuses)

    if percentage_complete == 1:
        activity.status = api_models.StatusType.objects.get(name_en="READY")
    elif percentage_complete > 0:
        activity.status = api_models.StatusType.objects.get(name_en="IN PROGRESS")
    else:
        activity.status = api_models.StatusType.objects.get(name_en="EMPTY")

    activity.completion_percentage = percentage_complete
    activity.save()

    return activity.status


# NOTE: This could be done with signals, but I saw there are no signals as of now
# so I kept this approach for consistency. Can be changed later if needed.
def get_activity_default_status():
    return api_models.StatusType.objects.get_or_create(name_en="EMPTY")[0]


def get_default_peat_type():
    return api_models.PeatType.objects.get_or_create(name_en="Nutrient Poor")[0]


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

    parent_module = None
    module_type = None

    for mt in organic_soil.activity.module_types.all():
        if mt.is_luc:
            parent_module = getattr(organic_soil.activity, mt.class_name.lower()).first()
            module_type = mt
            break
        else:
            potential_parent = getattr(organic_soil.activity, mt.class_name.lower(), None)
            if potential_parent:
                parent = potential_parent.first()
                if parent and getattr(parent, "organic_soil", None) == organic_soil:
                    parent_module = parent
                    module_type = mt
                    break

    if parent_module is None:
        raise ValueError("Organic Soil must be associated either with a Land Use Change or an independent Land Module")

    return parent_module, module_type


class ChangeLog:
    def __init__(self, date, user, reason, changes):
        self.date = date
        self.user = user
        self.reason = reason
        self.changes: list[Change] = changes


class Change:
    def __init__(self, field, old, new):
        self.field = field
        self.field_verbose_name = field.replace("_", " ").capitalize()
        self.old = old
        self.new = new


def get_changes(records: list[HistoricalRecords], exclude_fields: list[str] = None) -> list:
    changes = []
    for record in records:
        if record.prev_record is None:
            changes.append(ChangeLog(record.history_date, record.history_user.email, ChangeReasons.CREATE.value, []))
            continue

        if record.next_record is None:
            continue

        delta = record.diff_against(record.prev_record)
        fields_to_remove = [
            "last_cached_at",
            "cached_results_total",
            "cached_results_by_activity",
            "cached_results_by_gas",
            "cached_results_by_activity_by_gas",
            "last_modified",
            "status",
            "map_data",
        ] + (exclude_fields or [])
        delta.changes = [change for change in delta.changes if change.field not in fields_to_remove]

        # TODO: Check why history_user is None when history_type = "-", which likely means deletion
        if record.history_user is None:
            continue

        change_log: ChangeLog = ChangeLog(record.history_date, record.history_user.email, record.history_change_reason, [])
        for change in delta.changes:
            FieldClass = getattr(record, change.field).__class__
            if issubclass(FieldClass, models.Model):
                # If the field is a ForeignKey, get the related object
                if change.old and change.new:
                    try:
                        old_obj = FieldClass.objects.get(pk=change.old)
                        new_obj = FieldClass.objects.get(pk=change.new)
                        change_log.changes.append(Change(change.field, old_obj.name, new_obj.name))
                    except FieldClass.DoesNotExist:
                        change_log.changes.append(Change(change.field, change.old, change.new))
            else:
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


def get_entity_definitions(entity_type: str) -> dict:
    """
    Returns a dictionary where the key is the model's field name
    and the value is the translated verbose_name for that field.
    """
    # Get the model class from the entity_type string (assuming the entity_type matches the model name)
    try:
        model_class = apps.get_model("api", entity_type)
    except LookupError:
        raise ValueError(f"Model '{entity_type}' not found")
    # Extract the field names and their translated verbose names
    field_definitions = {
        field.name: _(field.verbose_name) if field.verbose_name else field.name for field in model_class._meta.get_fields() if hasattr(field, "verbose_name") and not field.name.endswith("_thread")
    }

    return field_definitions


def find_empty_scenarios(entity, field: str):
    if not isinstance(entity, api_models.Module) and not isinstance(entity, api_models.Submodule):
        raise ValueError("Entity must be a Module instance")

    entity: api_models.Module

    relevant_scenarios: list[ScenarioTypes] = entity.get_relevant_scenarios()

    missing = []

    for s in relevant_scenarios:
        # Dynamically construct the field name
        field_name = f"{field}_{s.value}"

        try:
            # Check if the field exists in the model using _meta
            entity._meta.get_field(field_name)

            if getattr(entity, field_name) is None:
                missing.append(s)
        except FieldDoesNotExist:
            raise ValueError(f"Field '{field_name}' not found in {entity.__class__.__name__}. Have you added or refactored the field name recently?")

    return [s.verbose_name for s in missing]


@dataclass
class DefaultValue:
    value: float = 0


def update_change_reason(instance, reason):
    from simple_history.utils import get_history_manager_for_model

    attrs = {}
    model = type(instance)
    manager = instance if instance.pk is not None else model
    history = get_history_manager_for_model(manager)
    history_fields = [field.attname for field in history.model._meta.fields]
    for field in instance._meta.fields:
        if field.attname not in history_fields:
            continue
        value = getattr(instance, field.attname)
        if field.primary_key is True:
            if value is not None:
                attrs[field.attname] = value
        else:
            attrs[field.attname] = value

    record = history.filter(id=instance.pk).order_by("-history_date").first()
    record.history_change_reason = reason
    record.save()


def validate_uuid(uuid_string):
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        return False
    return True


def send_changes_email(project: "api_models.Project", recipients: list["api_models.CustomUser"] = None) -> None:
    """
    Send an email to all Admin members with the changes made to the project.

    Args:
        project (Project): The project object.
        lock_holder (CustomUser): The user who holds the lock.
        last_lock_update_date (datetime): The date when the lock was last updated.
        recipients (list[CustomUser], optional): List of users to send the email to. If None, defaults to all Admin members of the project.

    Returns:
        None
    """

    def get_new_comments(threads: list["api_models.CommentThread"], locked_at: str) -> list:
        new_comments = []
        for thread in threads:
            if thread is None:
                continue
            comments = thread.comments.filter(date_created__gte=locked_at)
            if comments.exists():
                for comment in comments:
                    comment: "api_models.Comment"
                    changelog = ChangeLog(
                        date=comment.date_created,
                        user=None,
                        reason=ChangeReasons.UPDATE.value,
                        changes=[
                            Change(
                                field="comment",
                                old=None,
                                new=comment.content,
                            )
                        ],
                    )
                    new_comments.append(changelog)
        return new_comments

    if project.locked_at is None or project.locked_by is None:
        raise ValueError("last_lock_update_date and lock_holder are required. You are probably trying to send an email without a lock.")

    if recipients is None:
        from api.models import ProjectNotificationPreference

        # Get all admin members who haven't opted out globally
        potential_recipients = project.members.filter(group__name="Admin", user__is_opted_out_of_emails=False).all()

        # Filter out users who have opted out of notifications for this specific project
        recipients = []
        for member in potential_recipients:
            user = member.user
            project_preference = ProjectNotificationPreference.objects.filter(user=user, project=project).first()

            # If no project-specific preference exists, or if they haven't opted out for this project, include them
            if project_preference is None or not project_preference.is_opted_out:
                recipients.append(member)

    locked_at = project.locked_at

    fields_to_exclude = ["locked_at", "locked_by", "is_locked", "lock_updated_at"]

    changes = {
        "project": {
            "name": project.name,
            "changes": get_changes(project.history.filter(history_date__gte=locked_at), exclude_fields=fields_to_exclude),
        },
        "activities": [],
    }

    for a in project.activities.all():
        a_data = {"name": a.name, "changes": get_changes(a.history.filter(history_date__gte=locked_at), exclude_fields=fields_to_exclude), "modules": []}

        for m in find_modules(a):
            m: "api_models.Module" | "api_models.Submodule"
            m_changes = get_changes(m.history.filter(history_date__gte=locked_at), exclude_fields=fields_to_exclude)

            if hasattr(m, "submodules"):
                submodules = m.submodules
                for submodule in submodules:
                    submodule_changes = get_changes(submodule.history.filter(history_date__gte=locked_at), exclude_fields=fields_to_exclude)
                    if submodule_changes:
                        m_changes.extend(submodule_changes)

                    threads = submodule.threads
                    new_comments = get_new_comments(threads, locked_at)
                    if new_comments:
                        m_changes.extend(new_comments)

            threads = m.threads
            new_comments = get_new_comments(threads, locked_at)
            if new_comments:
                m_changes.extend(new_comments)

            if not m_changes:
                continue

            a_data["modules"].append({"name": m.__class__.__name__, "changes": m_changes})

        if len(a_data["changes"]) > 0 or len(a_data["modules"]) > 0:
            changes["activities"].append(a_data)

    lock_holder = project.members.filter(user=project.locked_by).first()
    if lock_holder is None:
        log.warning(f"Lock holder {project.locked_by} not found in project members. Lock holder does not belong to the project.")

    # Send email to recipients
    context = {
        "project": changes["project"],
        "project_url": f"{settings.FRONTEND_URL}/project/{project.id}/",
        "activities": changes["activities"],
        "lock_holder_group_name": lock_holder.group.name if lock_holder else "Superuser",
        "lock_holder_name": project.locked_by.get_full_name(),
        "lock_unlock_date": locked_at,
    }

    subject = f"{context['lock_holder_group_name']} Feedback - {context['project']['name']}"

    if len(changes["activities"]) == 0 and len(changes["project"]["changes"]) == 0:
        return

    for recipient in recipients:
        user: api_models.CustomUser = recipient.user
        context.update({"recipient": user})
        if user.email:
            html_message = render_to_string(os.path.join(settings.BASE_DIR, "api", "templates", "changes", "changes.html"), context)
            plain_message = strip_tags(html_message)
            from_email = settings.DEFAULT_FROM_EMAIL
            to = user.email
            try:
                send_mail(subject, plain_message, from_email, [to], html_message=html_message)
            except Exception as e:
                log.error(f"Failed to send email to {user.email}: {e}")


def paginated_parallel_response(queryset, request, process_function, paginator_class=None, max_workers=None, serializer_class=None, serializer_kwargs=None):
    """
    Generalized utility for handling paginated responses with parallel processing.
    
    Args:
        queryset: Django queryset to paginate and process
        request: Django request object
        process_function: Function to process each item (optional if serializer_class provided)
        paginator_class: Pagination class to use (defaults to DefaultPagination)
        max_workers: Maximum number of worker threads (defaults to None for automatic)
        serializer_class: Serializer class to use instead of process_function
        serializer_kwargs: Additional kwargs to pass to serializer
    
    Returns:
        Response: Paginated response with processed data
    """
    from concurrent.futures import ThreadPoolExecutor
    from rest_framework.pagination import PageNumberPagination
    from rest_framework import status as http_status
    
    # Use default pagination if none provided
    if paginator_class is None:
        # Import DefaultPagination from views to avoid circular imports
        from api.views import DefaultPagination
        paginator_class = DefaultPagination
    
    # Create processing function if serializer_class is provided
    if serializer_class is not None and process_function is None:
        serializer_kwargs = serializer_kwargs or {}
        def process_function(item):
            return serializer_class(item, **serializer_kwargs).data
    
    if process_function is None:
        raise ValueError("Either process_function or serializer_class must be provided")
    
    # Create paginator and paginate queryset
    paginator = paginator_class()
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        # Process page items in parallel
        executor_kwargs = {}
        if max_workers is not None:
            executor_kwargs['max_workers'] = max_workers
            
        with ThreadPoolExecutor(**executor_kwargs) as executor:
            response_data = list(executor.map(process_function, page))
        return paginator.get_paginated_response(response_data)
    
    # If no pagination, process all items
    if serializer_class is not None:
        serializer_kwargs = serializer_kwargs or {}
        response_data = serializer_class(queryset, many=True, **serializer_kwargs).data
    else:
        response_data = list(map(process_function, queryset))
    
    return Response(data=response_data, status=http_status.HTTP_200_OK)
