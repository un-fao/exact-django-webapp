from django.apps import apps
from rest_framework import exceptions

CN_RATIO_FOREST = 10
CN_RATIO_GRASSLAND = 15
MANGROVE_FACTOR = 0.451
NON_MANGROVE_FACTOR = 0.47
MANGROVES = 'Mangroves'

def snake_case(str):
    res = [str[0].lower()]
    for c in str[1:]:
        if c in ('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            res.append('_')
            res.append(c.lower())
        else:
            res.append(c)
     
    return ''.join(res)

def sanitize_for_model(str: str):
    return str.replace(" ", "").replace("-", "").replace("_", "")

def error(msg):
    return {'error': msg}

def get_model(name, app_name='api', suffix='Input'):
    return apps.get_model(app_name, sanitize_for_model(name+suffix))

def get_query_param_or_validation_error(request, param_name):
    param = request.query_params.get(param_name)
    if param is None:
        raise exceptions.ValidationError(f"{param_name} is required")
    return param