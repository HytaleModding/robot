from types import UnionType
from typing import Any, get_origin, get_args, Union


def is_union_type(type_: type) -> bool:
    """Whether the type is `typing.Union` with type arguments or shorthand `X | Y` (`types.UnionType`)."""
    return isinstance(type_, UnionType) or get_origin(type_) is Union


def is_optional_type(type_: type) -> bool:
    """Whether the type is `typing.Union` containing a `types.NoneType` in its type arguments."""
    return is_union_type(type_) and type(None) in get_args(type_)


def is_instantiable_collection_type(type_: type) -> bool:
    """Whether the type is an instantiable builtin collection (`dict`, `list`, `tuple`, `set`)."""
    origin = get_origin(type_) or type_
    return origin in (dict, list, tuple, set)


def is_instantiable_dict_type(type_: type) -> bool:
    """Whether the type is an instantiable `dict`."""
    return (get_origin(type_) or type_) is dict


def is_instantiable_list_type(type_: type) -> bool:
    """Whether the type is an instantiable `list`."""
    return (get_origin(type_) or type_) is list


def is_instantiable_tuple_type(type_: type) -> bool:
    """Whether the type is an instantiable `tuple`."""
    return (get_origin(type_) or type_) is tuple


def is_instantiable_set_type(type_: type) -> bool:
    """Whether the type is an instantiable `set`."""
    return (get_origin(type_) or type_) is set


def has_type_arguments(type_: type) -> bool:
    """Whether the type has type arguments."""
    return len(get_args(type_)) > 0


def get_type_arguments(type_: type) -> tuple[Any, ...]:
    """Get the type arguments of a type.

    Raises:
        ValueError: If type has no type arguments.
    """
    if not has_type_arguments(type_):
        raise ValueError("Type has no type arguments")

    return get_args(type_)


def try_get_type_arguments(type_: type, default_arguments: tuple) -> tuple[Any, ...]:
    """Try getting the type arguments of a type or return the given default arguments."""
    try:
        return get_type_arguments(type_)
    except ValueError:
        return default_arguments


def unwrap_optional_type(optional_type: type) -> Any:
    """Extract non-`types.NoneType` type arguments from a `typing.Optional` type.

    Returns:
        `typing.Union` type including all type arguments except `None`, or the only non-`types.NoneType` type argument.

    Raises:
        ValueError: If no non-`types.NoneType` is found.
    """
    type_args_without_none: list = [type_ for type_ in get_args(optional_type) if type_ is not type(None)]
    if len(type_args_without_none) == 0:
        raise ValueError("Could not find one or more non-NoneType type arguments")
    return Union[*type_args_without_none]


def convert_string_to_bool(value: str) -> bool:
    """Convert a string representation of a boolean to a `bool`.

    Raises:
        ValueError: If string is an invalid literal.
    """
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    elif value.lower() in ("false", "no", "0", "off"):
        return False
    else:
        raise ValueError(f"Invalid literal for converting string to bool: \"{value}\"")
