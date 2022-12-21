from django.apps import apps

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