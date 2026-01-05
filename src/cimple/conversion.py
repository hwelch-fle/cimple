from enum import EnumType
import json
from dataclasses import is_dataclass
from arcpy import (
    AsShape,
    SpatialReference,
    cim as arcpy_cim,
)
from datetime import datetime
import math

from ._build import check_cimple
# ensure cimple.cim is built
check_cimple(__file__)
from . import cim

# Encoders
class cimpleJSONEncoder(json.JSONEncoder):
    _cim = cim
    def default(self, o: object) -> object:
        if is_dataclass(o) and not isinstance(o, type):
            o_dict = o.__dict__.copy()
            o_dict['type'] = o.__class__.__name__
            return o_dict
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class cimJSONEncoder(cimpleJSONEncoder):
    _cim = arcpy_cim
    def default(self, o: object) -> object:
        return super().default(cim_to_cimple(o))

# Decoders      
class cimpleJSONDecoder(json.JSONDecoder):
    _cim = cim
    def __init__(self, *args: object, **kwargs: object):
        super().__init__(object_hook=self.hook, *args, **kwargs)
    
    def hook(self, obj: object) -> object:
        if isinstance(obj, dict):
            _type = obj.pop('type', None)
            
            # CIM Objects
            if cimple_obj := getattr(self._cim, str(_type), None):
                return cimple_obj(**{k: self.hook(v) for k, v in obj.items()})
            
            # Shapes
            elif 'spatialReference' in obj:
                return AsShape(obj, esri_json=True)
            
            # Spatial References
            elif 'wkid' in obj:
                return SpatialReference(obj['wkid'])
            
        elif isinstance(obj, list):
            return [self.hook(o) for o in obj]
        
        elif isinstance(obj, str):
            if obj == 'nan':
                return None
            elif obj == 'inf':
                return math.inf
            try:
                return datetime.fromisoformat(obj)
            except Exception:
                pass
        return obj

class cimJSONDecoder(cimpleJSONDecoder):
    _cim = arcpy_cim
    def hook(self, obj: object) -> object:
        return cimple_to_cim(super().hook(obj))

# cimple <--> json
def cimple_to_json(cimple_object: object, indent: int=4) -> str:
    """Convert a CIM object into a JSON string"""
    return json.dumps(cimple_object, indent=indent, cls=cimpleJSONEncoder)

def json_to_cimple(cimple_json: str) -> object:
    """Convert a json string into an initialized CIM object"""    
    return json.loads(cimple_json, cls=cimpleJSONDecoder)

# cimple <--> cim
def cimple_to_cim(cimple_obj: object | list[object]) -> object:
    if isinstance(cimple_obj, list):
        return [cimple_to_cim(o) for o in cimple_obj]
    cim_obj = getattr(arcpy_cim, cimple_obj.__class__.__name__, None)
    
    # Enums are in cim global namespace and shouldn't be initialized
    # The backend object creation will convert the string value to an int flag
    if cim_obj and not isinstance(cim_obj, EnumType):
        # CIM objects from the arcpy.cim module cannot be initialized with values
        # We need to initialize the object then update the instance __dict__
        cim_obj = cim_obj()
        cim_obj.__dict__.update({k: cimple_to_cim(v) for k, v in cimple_obj.__dict__.items()})
        return cim_obj
    return cimple_obj

def cim_to_cimple(cim_obj: object | list[object]) -> object:
    if isinstance(cim_obj, list):
        return [cim_to_cimple(o) for o in cim_obj]
    cimple_obj = getattr(cim, cim_obj.__class__.__name__, None)
    if cimple_obj:
        return cimple_obj(**{k: cim_to_cimple(v) for k, v in cim_obj.__dict__.items()})
    return cim_obj

# cim <--> json
def cim_to_json(cim_obj: object) -> str:
    return json.dumps(cim_obj, cls=cimJSONEncoder)

def json_to_cim(cim_json: str) -> object:
    return json.loads(cim_json, cls=cimJSONDecoder)