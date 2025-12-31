from collections import defaultdict
from enum import Enum, EnumType
from pathlib import Path
from types import ModuleType
from typing import Any

from arcpy import cim, version

__version__ = (0,0,1)

# Get version info from arcpy as tuple of ints (<major>, <minor>, <build>)
# Fallback to (0,0,0) if format is broken and __version__ info can't be determined
try:
    __arcpy_version__ = tuple(map(int,(*version.data['version'].split('.')[:2], version.build))) # type: ignore
except Exception:
    __arcpy_version__ = (0,0,0)

CIM_BUILT = Path('cim').exists()

# <Enum>: (str_name: val)
ParsedEnum = dict[Enum, tuple[str, Any]]
# __doc__, __dict__
ParsedCIM = tuple[str | None, dict[str, Any]]

four_spaces = '    '


def load(mod: ModuleType = cim) -> tuple[list[EnumType], list[type]]:
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


def parse_cim(cls: type):
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
    return {cls: (cls.__doc__, attrs)}


def enum_to_literal(enum: ParsedEnum) -> str:
    vals = list(name for name, _ in enum.values())
    return f'Literal{vals}'


def base_imports() -> list[str]:
    return [
        'from __future__ import annotations\n\n',
        'from dataclasses import (\n\tdataclass,\n\tfield as dc_field,\n)\n',
    ]


def modname(obj: type) -> str:
    return obj.__module__.split('.')[-1]


def write_literals(unique_enums: dict[EnumType, ParsedEnum]) -> set[str]:
    literals = {e.__name__ for e in unique_enums}
    with open('cim/literals.py', 'wt') as fl:
        fl.write('from typing import Literal\n')
        for e, parsed in unique_enums.items():
            lit = enum_to_literal(parsed)

            if lit == 'Literal[]':
                continue  # Skip Empty

            # Write block of Literal[str, ...], Literal[int, ...], dict[str, int]
            fl.write(f'\n# {e.__name__} Typing\n')
            fl.write(f'{e.__name__} = {lit}\n')
            fl.write(f'"""{(e.__doc__ or "NO DOC").strip()}\n\t{get_doc_link(e)}"""\n')
            fl.write(f'{e.__name__}_Map = {dict(parsed.values())}\n')
    return literals


def build_class_attrs(
    attrs: dict[str, Any], mods: dict[str, type], c: type
) -> tuple[list[str], dict[str, set[str]]]:
    class_string: list[str] = []
    imports: defaultdict[str, set[str]] = defaultdict(set)
    
    for name, val in attrs.items():
        _attr_type = type(val).__name__
        if isinstance(val, str) and val in mods:
            _attr_type = f'{val} = dc_field(default_factory=lambda: {val}())'
            if mods[val].__module__ != c.__module__ and val not in imports.get(
                modname(mods[val]), []
            ):
                if val not in imports[modname(mods[val])]:
                    imports[modname(mods[val])].add(val)
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
            _attr_type = 'float = nan'
            imports['math'].add('nan')
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
        elif 'CIMExternal' in repr(val):
            e_name = repr(val).split('.')[-1][:-2]
            _attr_type = f'{e_name} = {e_name}()'
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
    return [
        f'from {mod} import (\n{four_spaces}{f",\n{four_spaces}".join(sorted(classes))},\n)\n\n'
        for mod, classes in imps.items()
    ]


def get_doc_link(c: type) -> str:
    return f'https://github.com/Esri/cim-spec/blob/main/docs/v3/{modname(c)}.md#{c.__name__.lower()}-1'


def merge(
    root: dict[str, set[str]], trg: dict[str, set[str]]
) -> dict[str, set[str]]:
    for k in root:
        root[k] |= trg.get(k, set())
    for k in trg:
        root[k] = trg[k] | root.get(k, set())
    
    import_order = ['typing', 'math', 'datetime', 'CIM*', 'literals']
    _keys = list(root.keys())
    _sorted_root: dict[str, set[str]] = {}
    for mod in import_order:
        if mod in _keys:
            _sorted_root[mod] = root[mod]
        elif mod == 'CIM*':
          cim_mods = sorted(k for k in root.keys() if k.startswith('CIM'))
          for cim_mod in cim_mods:
              _sorted_root[cim_mod] = root[cim_mod]
    return _sorted_root


def format_doc(doc: str | None) -> str:
    doc = doc or 'NO DOC'
    return (
        doc.strip()
        .replace('\n', '')
        .replace('     ', ' ')
        .replace('///', f'\n{four_spaces}')
    )


def build_cim():
    enums, classes = load()
    Path('cim').mkdir(parents=True, exist_ok=True)
    unique_enums: dict[EnumType, ParsedEnum] = {}
    for enum in enums:
        unique_enums[enum] = parse_enum(enum)
    write_literals(unique_enums)

    unique_classes: dict[type, ParsedCIM] = {}
    for c in classes:
        unique_classes.update(parse_cim(c))
    class_modules: dict[str, str] = {c.__name__: modname(c) for c in unique_classes}
    mod_names = set(class_modules.values())
    class_names = {c.__name__: c for c in unique_classes}

    mod_files: dict[str, tuple[dict[str, set[str]], list[str], list[str]]] = {}
    for mod in mod_names:
        imports: dict[str, set[str]] = {}
        mod_classes: list[str] = []
        all_: list[str] = []
        # Base Module
        if mod == 'cim':
            continue

        for c, (doc, attrs) in filter(
            lambda m: modname(m[0]) == mod, unique_classes.items()
        ):
            attr_strs, class_imps = build_class_attrs(attrs, class_names, c)
            class_imps = {k: v for k, v in class_imps.items() if k != mod}
            imports = merge(imports, class_imps)
            all_.append(c.__name__)
            mod_classes.append(
                '\n'.join(
                    [
                        '@dataclass',
                        # Class Header
                        f'class {c.__name__}:',
                        # Doc
                        f'{four_spaces}"""{get_doc_link(c)}\n\n'
                        f'{four_spaces}{format_doc(doc)}'
                        f'\n{four_spaces}"""',
                        *attr_strs,
                        '\n',
                    ]
                )
            )
        mod_files[mod] = (imports, mod_classes, all_)

    for m_name, (imports, d_classes, all_) in mod_files.items():
        print(f'writing {m_name}')
        with open(f'cim/{m_name}.py', 'wt') as fl:
            fl.writelines(base_imports())
            fl.writelines(parse_imps(imports))
            fl.write(
                f'__all__ = [\n{four_spaces}{f",\n{four_spaces}".join([f"'{n}'" for n in all_])},\n]\n\n'
            )
            fl.writelines(d_classes)

    with open('cim/__init__.py', 'wt') as fl:
        for m in sorted(mod_files):
            fl.write(f'from {m} import *\n')
        fl.write(f'\n__cim_version__ = {__arcpy_version__}')

# If this module is imported and the cim submodule isn't generated, generate it
if not CIM_BUILT:
    build_cim()

elif CIM_BUILT:
    try:
        print('importing cim')
        from cim import __cim_version__
        if tuple(__cim_version__) < tuple(__arcpy_version__):
            build_cim()
    except Exception as e:
        print(e)
        build_cim()
        
elif __name__ == '__main__':
    build_cim()