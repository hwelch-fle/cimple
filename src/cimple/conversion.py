import json
from dataclasses import is_dataclass
from typing import Any
from arcpy import (
    AsShape,
    SpatialReference,
    cim as arcpy_cim,
)
from datetime import datetime
import math

try:
    from . import cim
except ImportError:
    cim = None

class JSONCIMEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o) and not isinstance(o, type):
            o_dict = o.__dict__.copy()
            o_dict['type'] = o.__class__.__name__
            return o_dict
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
        
class JSONCIMDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.hook, *args, **kwargs)
    
    def hook(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            _type = obj.pop('type', None)
            
            # CIM Objects
            if cimple_obj := getattr(cim, str(_type), None):
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

def cim_to_json(cim_object: object, indent: int=4) -> str:
    """Convert a CIM object into a JSON string"""
    return json.dumps(cim_object, indent=indent, cls=JSONCIMEncoder)

def json_to_cim(cim_json: str) -> Any:
    """Convert a json string into an initialized CIM object"""    
    return json.loads(cim_json, cls=JSONCIMDecoder)

def cim_to_cimple(cim_obj: Any) -> Any:
    if isinstance(cim_obj, list):
        return [cim_to_cimple(o) for o in cim_obj]
    cimple_obj = getattr(cim, cim_obj.__class__.__name__, None)
    if cimple_obj:
        return cimple_obj(**{k: cim_to_cimple(v) for k, v in cim_obj.__dict__.items()})
    return cim_obj

def cimple_to_cim(cimple_obj: Any) -> Any:
    if isinstance(cimple_obj, list):
        return [cimple_to_cim(o) for o in cimple_obj]
    cim_obj = getattr(arcpy_cim, cimple_obj.__class__.__name__, None)
    if cim_obj:
        # CIM objects from the arcpy.cim module cannot be initialized with values
        # We need to initialize the object then update the instance __dict__
        cim_obj = cim_obj()
        cim_obj.__dict__.update({k: cimple_to_cim(v) for k, v in cimple_obj.__dict__.items()})
        return cim_obj
    return cimple_obj
    