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

def get_invalid_keys(a: object, b: object) -> dict[str, Any]:
    a = a.__dict__
    b = b.__dict__
    return {
        k: (a[k], b.get(k))
        for k in a
        if k not in b
        or not any([a[k] == b[k], a[k] is b[k]])
    }

def test_json_roundtrip():
    for o in get_cim_objs():
        a = o()
        b = json_to_cim(cim_to_json(a))
        assert a == b, get_invalid_keys(a, b)
    print(f'json <--> CIM valid')

def test_cim_roundtrip():
    for o in get_cim_objs():
        a = o()
        b = cim_to_cimple(cimple_to_cim(a))
        assert a == b, get_invalid_keys(a, b)
    print(f'cimple <--> CIM valid')

if __name__ == '__main__':
    # Failing due to Literals
    #test_cim_roundtrip()
    test_json_roundtrip()    