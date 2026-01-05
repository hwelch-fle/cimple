
from ._build import check_cimple, __version__, __arcpy_version__
check_cimple(__file__)

from .cim import *

# Because the json conversions for cimple and cim are identical
# cim_to_json and json_to_cim are implemented using cimple objects
# as an intermediary

from .conversion import (
    cimpleJSONDecoder as cimpleJSONDecoder, 
    cimpleJSONEncoder as cimpleJSONEncoder,
    cimJSONEncoder as cimJSONEncoder,
    cimJSONDecoder as cimJSONDecoder,
    
    # cimple json converters
    json_to_cimple as json_to_cimple, 
    cimple_to_json as cimple_to_json, 
    
    # cimple cim converters
    cim_to_cimple as cim_to_cimple,
    cimple_to_cim as cimple_to_cim,
    
    # cim json converters
    cim_to_json as cim_to_json,
    json_to_cim as json_to_cim,
)

if __name__ == '__main__':
    # rebuild the cim when run
    from ._build import build_cim
    build_cim()