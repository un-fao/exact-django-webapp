CN_RATIO_CROPLAND = 10
CN_RATIO_FOREST = 15
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