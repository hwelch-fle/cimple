from pathlib import Path
from ._build import (
    build_cim as _build_cim,
    __version__,
    __arcpy_version__,
)

_CIM_BUILT = (Path(__file__).parent / 'cim').exists()

# If this module is imported and the cim submodule isn't generated, 
# generate it
if not _CIM_BUILT:
    print(f'Building cimple.cim')
    _build_cim()

elif _CIM_BUILT:
    try:
        from .cim import (
            __cim_version__, 
            __version__ as __existing_version__,
        )
        if (
            __cim_version__ < __arcpy_version__  # type: ignore
            or 
            __existing_version__ < __version__
        ):
            print(f'Updating cimple.cim')
            _build_cim()
    except Exception as e:
        print(e)
        print(f'Rebuilding cimple.cim')
        _build_cim()

from .cim import *