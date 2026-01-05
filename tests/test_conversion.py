import datetime
from enum import Enum
import sys
from pathlib import Path

sys.path.append('../src')

try:
    import arcpy as arcpy
except ImportError:
    print('Importing Arcpy...')
    sys.path.append(str(Path(r'C:\Program Files\ArcGIS\Pro\Resources\ArcPy')))
    import arcpy

from dataclasses import is_dataclass
from typing import Any
from cimple import (
    cim_to_json, 
    json_to_cim,
    cim_to_cimple,
    cimple_to_cim,
)
from cimple import cim

def get_cim_objs(): # type: ignore
    yield from filter(
        lambda o: hasattr(o, '__module__') and is_dataclass(o), 
        (getattr(cim, o) for o in dir(cim) if o.startswith('CIM'))
    )

# CIM defaults set enum values, but getDefinition returns string literals
# So we can validate the type by checking the default enum name attribute
# against the cimple string literal

# CIM object references are stored as strings in default 
# initialized arcpy.cim objects, so the class name needs to be checked

# When checking cim roundtrip, the cim object is initialized after the 
# cimple object, so the creation time drifts by ~100 microseconds
# to prevent false positives on __eq__ checks, these are truncated to 
# seconds

def norm(o: object) -> Any:
    # CIM Enums can be set using name attribute
    if isinstance(o, Enum):
        return o.name
    
    # arcpy.cim stores object reference as string name
    if isinstance(o, cim._base.CIMBase):
        return o.__class__.__name__
    
    # CIMExternal stores class reference in arcpy.cim
    if isinstance(o, type):
        # CIMExternal objects are stored as a type reference
        if 'CIMExternal' in repr(o):
            return o.__name__
        
        # arcobjects are defaulted to None in cimple
        # arcpy.cim stores class reference
        if 'arcobjects' in repr(o):
            return None
        
    # cimple defaults object reference to None
    # arcpy.cim defaults object()
    if repr(o).startswith('<object object'):
        return None
    
    # cimple converts nan to None
    if repr(o) == 'nan':
        return None
    
    # Initialization time for CIM roundtrip causes a timestamp mismatch
    # dropping the last 2 digits from the timestamp will prevent this from
    # failing as often, but if the script is run when the UNIX timestamp is
    # xxxx999, the check will fail. To prevent this, the tests should be run 
    # multiple times and if it passes once, it should be considered valid
    if isinstance(o, datetime.datetime):
        return round(o.timestamp(), -2)
    return o

def get_invalid_keys(a: object, b: object) -> dict[str, Any]:
    a = {k: norm(v) for k, v in a.__dict__.items()}
    b = {k: norm(v) for k, v in b.__dict__.items()}
    return {
        k: (a[k], b.get(k))
        for k in a
        if k not in b
        or not any([a[k] == b[k], a[k] is b[k]])
    }

def test_json_roundtrip():
    errors = 0
    print('Testing JSON roundtrip')
    for o in get_cim_objs():
        try:
            a = o()
            b = json_to_cim(cim_to_json(a))
            assert a == b, f'{type(a)}: {get_invalid_keys(a, b)}'
        except Exception as e:
            errors += 1
            print('\t'f'{o.__name__}: {e}')
    if not errors:
        print('\t'f'json <--> CIM valid')
    else:
        print('\t'f'json <--> CIM: {errors} errors')

def test_cim_roundtrip():
    errors = 0
    print('Testing CIM roundtrip')
    for o in get_cim_objs():
        try:
            a = o()
            b = cim_to_cimple(cimple_to_cim(a))
            raw_eq = a == b
            norm_eq = not bool(get_invalid_keys(a, b))
            assert norm_eq or raw_eq, f'{type(a)}: {get_invalid_keys(a, b)}'
        except Exception as e:
            errors += 1
            print('\t'f'{o.__name__}: {e}')
    if not errors:
        print('\t'f'cimple <--> CIM valid')
    else:
        print('\t'f'cimple <--> CIM {errors} errors')

if __name__ == '__main__':
    test_cim_roundtrip()
    test_json_roundtrip()