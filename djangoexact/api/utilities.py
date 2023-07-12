from django.apps import apps
from rest_framework import exceptions
import re
from api.models import Model
from rest_framework.response import Response
from rest_framework import status


CN_RATIO_FOREST = 10
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


def get_assessment_or_parent(module) -> tuple[Model, str]:
    """
    Looks for the assessment class in the module and returns a tuple (module, relationship).
    Returns (None, None) if no assessment class is found.
    """

    relative = (None, None)

    # NOTE: To add new assessments, make sure you follow the naming convention of the Assessment class in models.py
    # NOTE: Refer to documentation for more information (WIP)
    for attr in dir(module):
        if getattr(module, attr, None) is not None:
            if "_assessment" in attr:
                relative = (getattr(module, attr), "child")
                break
            # Matches all attributes with 'parent_' prefix and not ending with '_id'
            elif re.match("parent_[^_]*[^_id]", attr):
                relative = (getattr(module, attr), "parent")
                break

    return relative


def get_assessment_or_parent_(module) -> tuple[Model, str]:
    """
    Looks for the assessment class in the module and returns a tuple (module, relationship).
    Returns (None, None) if no assessment class is found.
    """

    relative = (None, None)

    # NOTE: To add new assessments, make sure you follow the naming convention of the Assessment class in models.py
    # NOTE: Refer to documentation for more information (WIP)
    for attr in dir(module):
        if getattr(module, attr, None) is not None:
            if "_assessment" in attr:
                relative = (getattr(module, attr), "child")
                break
            # Matches all attributes with 'parent_' prefix and not ending with '_id'
            elif re.match("parent_[^_]*[^_id]", attr):
                relative = (getattr(module, attr), "parent")
                break

    return relative


def get_url_name(model_name):
    url_name = model_name

    # regex split on non consecutive capital letters
    url_name = "".join(
        [f"-{x}" for x in re.split(r"(?<!^)(?=[A-Z](?![A-Z]|$))", url_name)]
    ).lower()
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
