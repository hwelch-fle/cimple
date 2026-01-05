from collections import defaultdict
from enum import Enum, EnumType
from pathlib import Path
from types import ModuleType
from typing import Any

from arcpy import (
    cim as _cim, 
    version as _version,
)

__version__ = (0,0,1)
MOD_ROOT = Path(__file__).parent

# Get version info from arcpy as tuple of ints (<major>, <minor>, <build>)
# Fallback to (0,0,0) if format is broken and __version__ info can't be determined
try:
    __arcpy_version__ = tuple(map(int,(*_version.data['version'].split('.')[:2], _version.build))) # type: ignore
except Exception:
    print('failed to determine arcpy version')
    __arcpy_version__ = (0,0,0)

# <Enum>: (str_name: val)
ParsedEnum = dict[Enum, tuple[str, Any]]

four_spaces = '    '


def load(mod: ModuleType = _cim) -> tuple[list[EnumType], list[type]]:
    modules: list[ModuleType] = [mod]
    enums: list[EnumType] = []
    classes: list[type] = []
    while modules:
        mod = modules.pop()
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
            obj = getattr(mod, attr)
            match obj:
                case ModuleType():
                    modules.append(obj)
                case EnumType():
                    enums.append(obj)
                case type():
                    classes.append(obj)
                case _:
                    continue
    return enums, classes


def parse_enum(enum: EnumType):
    return {m: (m.name, m.value) for m in enum._value2member_map_.values()}


def parse_cim(cls: type) -> tuple[type, dict[str, Any]]:
    attrs = {}
    try:
        attrs: dict[str, Any] = cls().__dict__
    except Exception as e:
        # This should only be CIMKGTimeWindow which is malformed
        attrs = {'ERROR': e}
        cls.__doc__ = f'Error parsing CIM: {e}'
        if cls.__name__ == 'CIMKGTimeWindow':
            attrs = {'minTime': 0, 'maxTime': 0}
        pass
    return cls, attrs


def enum_to_literal(enum: ParsedEnum) -> str:
    vals = list(name for name, _ in enum.values())
    return f'Literal{vals}'


def base_imports() -> list[str]:
    return [
        'from __future__ import annotations\n\n',
        f'from dataclasses import (\n{four_spaces}dataclass,\n{four_spaces}field as dc_field,\n)\n',
        f'from ._base import CIMBase\n\n'
    ]


def modname(obj: type) -> str:
    return obj.__module__.split('.')[-1]


def build_literals(enums: dict[EnumType, ParsedEnum]) -> list[str]:
    literal_strings: list[str] = []
    for e, parsed in enums.items():
        lit = enum_to_literal(parsed)
        if lit == 'Literal[]':
            continue  # Skip Empty
        # Write block of Literal[str, ...], Literal[int, ...], dict[str, int]
        literal_strings.append(f'\n# {e.__name__} Typing\n')
        literal_strings.append(f'{e.__name__} = {lit}\n')
        literal_strings.append(f'"""{(e.__doc__ or "NO DOC").strip()}\n{four_spaces}"""\n')
        literal_strings.append(f'{e.__name__}_Map = {dict(parsed.values())}\n')
    return literal_strings


def write_literals(unique_enums: dict[EnumType, ParsedEnum]) -> None:
    (MOD_ROOT / 'cim/literals.py').write_text(
        ''.join(
            [
                'from typing import Literal\n',
                *build_literals(unique_enums),
            ]
        )
    )


def build_class_attrs(attrs: dict[str, Any], mods: dict[str, type], c: type) -> tuple[list[str], dict[str, set[str]]]:
    class_string: list[str] = []
    imports: defaultdict[str, set[str]] = defaultdict(set)
    
    for name, val in attrs.items():
        _attr_type = type(val).__name__
        
        # Handle CIM objects (get from cc if not in same module)
        if isinstance(val, str) and val in mods:
            if mods[val].__module__ != c.__module__:
                _attr_type = f'cc.{val} = dc_field(default_factory=lambda: cc.{val}())'
                if val not in imports.get(modname(mods[val]), []):
                    imports[modname(mods[val])].add(val)
            else:
                _attr_type = f'{val} = dc_field(default_factory=lambda: {val}())'
                
        elif isinstance(val, Enum):
            _attr_type = f"{type(val).__name__} = '{val.name}'"
            imports['literals'].add(type(val).__name__)
            
        elif isinstance(val, list):
            _attr_type = 'list[Any] = dc_field(default_factory=list[Any])'
            imports['typing'].add('Any')
            
        elif isinstance(val, dict):
            _attr_type = 'dict[str, Any] = dc_field(default_factory=dict[str, Any])'
            imports['typing'].add('Any')
            
        elif isinstance(val, str):
            _attr_type = f'str = {val or "''"}'
            
        elif val is None:
            _attr_type = 'Any = None'
            
        elif _attr_type == 'datetime':
            _attr_type = 'datetime = dc_field(default_factory=datetime.now)'
            imports['datetime'].add('datetime')
            
        elif isinstance(val, bool):
            _attr_type = f'bool = {val}'
            
        elif isinstance(val, int):
            _attr_type = f'int = {val}'
            
        elif repr(val) == 'nan':
            # Avoid using math.nan because it breaks equality checks
            _attr_type = 'float | None = None'
            #imports['math'].add('nan')
            
        elif repr(val) == 'inf':
            _attr_type = 'float = inf'
            imports['math'].add('inf')
            
        elif isinstance(val, float):
            _attr_type = f'float = {val}'
            
        elif repr(val).endswith("Polygon'>"):
            _attr_type = 'Polygon | None = None'
            imports['arcpy'].add('Polygon')
            
        elif repr(val).endswith("Extent'>"):
            _attr_type = 'Extent | None = None'
            imports['arcpy'].add('Extent')
            
        elif repr(val).endswith("Polyline'>"):
            _attr_type = 'Polyline | None = None'
            imports['arcpy'].add('Polyline')
            
        elif repr(val).endswith("Geometry'>"):
            _attr_type = 'Geometry | None = None'
            imports['arcpy'].add('Geometry')
            
        elif repr(val).endswith("SpatialReference'>"):
            _attr_type = 'SpatialReference | None = None'
            imports['arcpy'].add('SpatialReference')
            
        elif repr(val).endswith("Multipoint'>"):
            _attr_type = 'Multipoint | None = None'
            imports['arcpy'].add('Multipoint')
            
        elif repr(val).endswith("Point'>"):
            _attr_type = 'Point | None = None'
            imports['arcpy'].add('Point')
        
        # Special Case for CIMExternal
        elif 'CIMExternal' in repr(val):
            e_name = repr(val).split('.')[-1][:-2]
            _attr_type = f'{e_name} = dc_field(default_factory=lambda: {e_name}())'
            imports['CIMExternal'].add(e_name)
            
        elif _attr_type == 'object':
            _attr_type = 'Any = None'
            
        else:
            print(f'WARNING: {val} cannot be parsed Using `Any` with `None` default!')
            _attr_type = 'Any = None'
            imports['typing'].add('Any')
            
        class_string.append(f'{four_spaces}{name}: {_attr_type}')
    return class_string, imports


def parse_imps(imps: dict[str, set[str]]) -> list[str]:
    has_cim = bool(imps.pop('._CIMCommon', False))
    return [
        f'from .{mod} import (\n{four_spaces}{f",\n{four_spaces}".join(sorted(classes))},\n)\n\n'
        if mod.startswith('CIM') or mod == 'literals' else
        f'from {mod} import (\n{four_spaces}{f",\n{four_spaces}".join(sorted(classes))},\n)\n\n'
        for mod, classes in imps.items()
    ] + (['from . import _CIMCommon as cc\n\n'] if has_cim else [])


def get_doc_link(c: type) -> str:
    return f'https://github.com/Esri/cim-spec/blob/main/docs/v3/{modname(c)}.md#{c.__name__.lower()}-1'


def merge(root: dict[str, set[str]], trg: dict[str, set[str]]) -> dict[str, set[str]]:
    for k in root:
        root[k] |= trg.get(k, set())
    for k in trg:
        root[k] = trg[k] | root.get(k, set())
    
    import_order = ['typing', 'math', 'datetime', 'arcpy', 'CIM*', 'literals']
    _keys = list(root.keys())
    _sorted_root: dict[str, set[str]] = {}
    for mod in import_order:
        if mod in _keys:
            _sorted_root[mod] = root.pop(mod)
        elif mod == 'CIM*':
            #continue
            cim_mods = sorted(k for k in root.keys() if k.startswith('CIM'))
            for cim_mod in cim_mods:
                _sorted_root[cim_mod] = root.pop(cim_mod)
    return _sorted_root


def format_doc(doc: str | None) -> str:
    doc = doc or 'NO DOC'
    return (
        doc.strip()
        .replace('\n', '')
        .replace('     ', ' ')
        .replace('///', f'\n{four_spaces}')
    )


def format_all(expose_names: list[str]) -> str:
    return f'__all__ = [\n{four_spaces}{f",\n{four_spaces}".join([f"'{n}'" for n in expose_names])},\n]\n\n'


def build_dataclass(cls: type, attrs: list[str]) -> str:
    return '\n'.join(
        [
            '@dataclass',
            # Class Header
            f'class {cls.__name__}(CIMBase):',
            # Doc
            f'{four_spaces}"""{get_doc_link(cls)}\n\n'
            f'{four_spaces}{format_doc(cls.__doc__)}'
            f'\n{four_spaces}"""',
            *attrs,
            '\n',
        ]
    )

def build_meta_class() -> str:
    return """class CIMMeta(type):
    def __subclasscheck__(cls, subclass: type) -> bool:
        cls_fields: dict[str, Any]|None = getattr(cls, '__dataclass_fields__', None)
        sub_fields: dict[str, Any]|None = getattr(subclass, '__dataclass_fields__', None)
        if cls_fields is None or sub_fields is None:
            return False
        return cls_fields.keys() <= sub_fields.keys()
    
    def __instancecheck__(self, instance: object) -> bool:
        return issubclass(type(instance), self)"""

def build_base_class() -> str:
    return """class CIMBase(metaclass=CIMMeta): ...
    """
def build_cim():
    enums, classes = load()
    (MOD_ROOT / 'cim').mkdir(parents=True, exist_ok=True)
    unique_enums: dict[EnumType, ParsedEnum] = {}
    for enum in enums:
        unique_enums[enum] = parse_enum(enum)
    write_literals(unique_enums)

    unique_classes = dict(parse_cim(c) for c in classes)
    class_modules: dict[str, str] = {c.__name__: modname(c) for c in unique_classes}
    mod_names = set(class_modules.values())
    class_names = {c.__name__: c for c in unique_classes}

    mod_files: dict[str, tuple[dict[str, set[str]], list[str], list[str]]] = {}
    for mod in mod_names:
        if mod == 'cim':
            continue
        
        imports: dict[str, set[str]] = {}
        mod_classes: list[str] = []
        all_: list[str] = []
        for c, attrs in unique_classes.items():
            if modname(c) != mod:
                continue 
            attr_strs, class_imps = build_class_attrs(attrs, class_names, c)
            class_imps = {k: v for k, v in class_imps.items() if k != mod}
            imports = merge(imports, class_imps)
            all_.append(c.__name__)
            mod_classes.append(build_dataclass(c, attr_strs))
        
        # Skip importing directly from module and instead import from aliased _CIMCommon
        for cim_mod in list(imports):
            if cim_mod.startswith('CIM') and cim_mod != 'CIMExternal':
                if '._CIMCommon' not in imports:
                    imports['._CIMCommon'] = {'._CIMCommon as cc'}
                imports.pop(cim_mod)
        mod_files[mod] = (imports, mod_classes, all_)

    # Write Submodules
    for m_name, (imports, d_classes, all_) in mod_files.items():
        print(f'writing {m_name}')
        (MOD_ROOT / f'cim/{m_name}.py').write_text(
            ''.join(
                [
                    *base_imports(),
                    *parse_imps(imports),
                    format_all(all_),
                    *d_classes,
                ]
            )
        )
    
    (MOD_ROOT / 'cim/_base.py').write_text(
        ''.join(
            [
                build_meta_class(),
                '\n\n',
                build_base_class(),
            ]
        )
    )
    
    # Write _CIMCommon
    (MOD_ROOT / 'cim/_CIMCommon.py').write_text(
        ''.join(
            [
                *[f'from .{m} import *\n' for m in sorted(mod_files)],
            ]
        )
    )
    
    # Write cim.__init__
    (MOD_ROOT / 'cim/__init__.py').write_text(
        ''.join(
            [
                # Import __all__
                *[f'from .{m} import *\n' for m in sorted(mod_files)],
                
                # Version Info
                f'\n# CIM Build',
                f'\n__cim_version__ = {__arcpy_version__}',
                f'\n# cimple Version',
                f'\n__version__ = {__version__}',
            ]
        )
    )
    
def check_cimple(root: str):
    _CIM_BUILT = (Path(root).parent / 'cim').exists()

    # If this module is imported and the cim submodule isn't generated, 
    # generate it
    if not _CIM_BUILT:
        print(f'Building cimple.cim')
        build_cim()

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
                build_cim()
        except Exception as e:
            print(e)
            print(f'Rebuilding cimple.cim')
            build_cim()