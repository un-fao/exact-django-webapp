from .models import *
from ..ipcc.models import *

def get_defaults(input: Model) -> dict:
    """
    Gets the default tier2 values for a given module.
    """
    try:
        func = f"calc_{input.__class__.__name__.lower()}_result"
        return globals()[func](input)
    except KeyError:
        raise Exception(f"Module '{input.__class__.__name__}' not (yet) supported.")
    except Exception as ex:
        raise ex

def get_annualcropping_defaults(input: AnnualCropping) -> dict:
    """
    Gets the default tier2 values for an AnnualCropping module.
    """

    pass