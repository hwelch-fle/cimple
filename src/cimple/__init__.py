
from ._build import check_cimple, __version__, __arcpy_version__
check_cimple(__file__)

from .cim import *
from .conversion import (
    json_to_cim as json_to_cim, 
    cim_to_json as cim_to_json, 
    JSONCIMDecoder as JSONCIMDecoder, 
    JSONCIMEncoder as JSONCIMEncoder,
    cim_to_cimple as cim_to_cimple,
    cimple_to_cim as cimple_to_cim,
)

if __name__ == '__main__':
    # rebuild the cim when run
    from ._build import build_cim
    build_cim()