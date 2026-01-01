import dataclasses
import inspect
import json
import logging
from dataclasses import is_dataclass, fields, MISSING, Field, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar, get_args, TYPE_CHECKING, Self, Callable
from json.decoder import JSONDecodeError

from settings import Settings
from utils.typing_utils import (
    is_union_type,
    is_optional_type,
    is_instantiable_collection_type,
    is_instantiable_dict_type,
    is_instantiable_list_type,
    is_instantiable_tuple_type,
    is_instantiable_set_type,
    try_get_type_arguments,
    unwrap_optional_type,
    convert_string_to_bool
)
from .model import ConfigSchema

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Static type checking only, ignored at runtime
    from _typeshed import DataclassInstance

    DataclassT = TypeVar("DataclassT", bound=DataclassInstance)
else:
    DataclassT = TypeVar("DataclassT")

# Static constants, not intended to be changed.
_CONFIG_PATH: Path =  Path(__file__).parent.parent / "config.json"
_CONFIG_TEMPLATE_PATH: Path =  Path(__file__).parent.parent / "config_template.json"

# ==================================================
# Context
# ==================================================

class ConfigLoadingMode(Enum):
    """The config loading mode describes how to load a value for a field."""
    STRICT = "strict"
    """STRICT config loading, fails on first value that cannot be loaded.
    
    Try to resolve a value from data. This might fail if the key is missing in the data or if the data for that key cannot be converted to the field's expected type.
    If that fails try to load a field's default value. This might fail because the field doesn't have a default value.
    If that fails raise a ConfigLoaderFieldException.
    """
    LENIENT = "lenient"
    """LENIENT config loading, does not fail and force loads an empty-like value if a value cannot be loaded.
    
    Let a value load in strict mode.
    If a ConfigLoaderFieldException is to be raised, instead force load an empty-like value.
    
    An empty-like value is a leniently loaded dataclass, an empty collection, or None regardless of the field's type.
    """
    TEMPLATE = "template"
    """TEMPLATE config loading, does not fail and force loads an template value if a value cannot be loaded.

    Let a value load in strict mode.
    If a ConfigLoaderFieldException is to be raised, instead force load an template value.

    A template value is an info string signaling that this field could not be loaded, including:
        - A default value if present
        - Field documentation if present in the field's metadata 
        - One or more example values if present in the field's metadata.
    
    This mode is intended for generating a template file from a loaded config instance.
    """


@dataclass(frozen=True)
class Context:
    loading_mode: ConfigLoadingMode = ConfigLoadingMode.STRICT
    """The config loading mode to use.
    
    Defaults to STRICT.
    """
    currently_resolving_path: tuple[tuple[Any, ...], ...] = ()
    """A path of keys and indexes to describe what value is currently being resolved.
    
    Each segment contains a key as the first value, as well as a various amount of indexes as trailing values.
    """
    contextual_logger: Callable[[object, Self], None] | None = None
    """A function to handle logging of an object based on context.
    
    If unset default logger is used which logs all errors as warnings except when generating a template file.
    """

    def push_key(self, key: str) -> Self:
        """Push a new segment containing a key to currently_resolving_path."""
        return Context(
            self.loading_mode,
            (*self.currently_resolving_path, (key,)),
            self.contextual_logger
        )

    def append_index(self, index: Any) -> Self:
        """Append an index in the last segment.

        An index might be anything that does not directly represent a dataclass field,
        like an index for a list or a tuple, or a key for a dict.

        Raises:
            ValueError: If currently_resolving_path has no keys.
        """
        if not self.currently_resolving_path:
            raise ValueError("Cannot append index to empty currently_resolving_path")

        return Context(
            self.loading_mode,
            (*self.currently_resolving_path[:-1], (*self.currently_resolving_path[-1], index)),
            self.contextual_logger
        )

    def force_loading_mode(self, mode: ConfigLoadingMode) -> Self:
        """Forcefully set config loading mode."""
        return Context(
            mode,
            self.currently_resolving_path,
            self.contextual_logger
        )

    def stringify_currently_resolving_path(self, slice_last_n_segments: int = 0) -> str:
        """Return currently_resolving_path as a string.

        Examples:
            - cogs.tags.tags['bot'].url
            - cogs.languages.proof_reader_user_ids['German'][0]

        Args:
            slice_last_n_segments (int): How many segments to slice off from the end.
                1 would mean the current key will be sliced off, making its parent the last key,
                2 would mean the parent of the parent is the last key, etc.
                Defaults to 0.

        Returns:
            str: A dot separated list of segments containing a key with zero or more indexes.
                If the output is empty return '<root>' instead.
        """
        if not self.currently_resolving_path or len(self.currently_resolving_path) <= slice_last_n_segments:
            return "<root>"

        segments = (
            self.currently_resolving_path
            if slice_last_n_segments == 0
            else self.currently_resolving_path[:-slice_last_n_segments]
        )

        return ".".join(
            segment[0] + "".join(
                f"[{repr(index)}]"
                for index in segment[1:]
            )
            for segment in segments
        )

# ==================================================
# Errors
# ==================================================

class ConfigLoaderException(Exception):
    """Raised when config loading fails for a different reason than a ConfigLoaderFieldException."""
    def __init__(self, context: Context, reason: str | None = None):
        self.context = context
        self.reason = reason

    def __str__(self) -> str:
        return f"Failed to load config{(": " + self.reason) if self.reason else ""}"


class ConfigLoaderFieldException(ConfigLoaderException):
    """Raised when a dataclass field cannot be resolved and a default value does not exist.

    Will not get raised in lenient mode as instead an empty-like value will be set depending on the type of the field.
    """
    def __init__(self, context: Context):
        super().__init__(context)

    def __str__(self) -> str:
        return (
            f"Failed to load config because a dataclass field could not be resolved. View the log for more information."
            f" Failed at path '{self.context.stringify_currently_resolving_path()}'"
        )


class ResolveValueError(Exception):
    def __init__(self, context: Context, type_: type, data: Any, reason: str):
        self.context = context
        self.type_ = type_
        self.data = data
        self.reason = reason

    def __str__(self) -> str:
        return (
            f"Unresolved value at path '{self.context.stringify_currently_resolving_path()}'"
            f" with expected type '{_stringify_type(self.type_)}': {self.reason}. Falling back to default value."
            f"\n  Read data: {repr(self.data)}"
        )


class UnresolvedAndDefaultValueMissingError(Exception):
    def __init__(self, context: Context, field: Field[Any], dataclass_type: type[DataclassT]):
        self.context = context
        self.field = field
        self.dataclass_type = dataclass_type

    def __str__(self) -> str:
        return (
            f"No default value for unresolved dataclass field"
            f" '{_stringify_type(self.dataclass_type)}.{self.field.name}'"
            f" at path '{self.context.stringify_currently_resolving_path(1)}.{self.field.name}'"
        )

# ==================================================
# Config Loading and Template File Creation
# ==================================================

def load_config(context: Context | None = None) -> ConfigSchema:
    """Load ConfigSchema from the config file and return it.

    Raises:
        ConfigLoaderException: If config loading fails.
    """
    config_loading_mode = (
        ConfigLoadingMode.LENIENT
        if Settings.get().LENIENT_CONFIG_LOADING
        else ConfigLoadingMode.STRICT
    )
    context = context or Context(config_loading_mode)

    if not _CONFIG_PATH.exists():
        create_template_file({}, context)
        raise ConfigLoaderException(context, "Did not find config file.")
    try:
        config_data: object = _read_from_file(_CONFIG_PATH)
    except JSONDecodeError as decodeErr:
        raise ConfigLoaderException(context, f"Check you JSON file for invalid syntax: {str(decodeErr)}")

    try:
        return _resolve_dataclass_value(ConfigSchema, config_data, context)
    except ConfigLoaderException:
        create_template_file(config_data, context)
        raise
    except Exception as e:
        create_template_file(config_data, context)
        raise ConfigLoaderException(context, str(e))


def create_template_file(data: Any | None = None, context: Context | None = None) -> None:
    """Load an instance of ConfigSchema in TEMPLATE loading mode and write its data as a dict to the template file.

    Force TEMPLATE config loading mode.
    """
    context = context or Context(ConfigLoadingMode.TEMPLATE)
    config_instance: ConfigSchema = _resolve_dataclass_value(
        ConfigSchema,
        data or {},
        context.force_loading_mode(ConfigLoadingMode.TEMPLATE)
    )
    _write_to_file(dataclasses.asdict(config_instance), _CONFIG_TEMPLATE_PATH)
    log.warning(
        f"A template config file was generated because the config file was missing or a required key could not be loaded."
        f" You can fill out the generated template file at `{_CONFIG_TEMPLATE_PATH}`"
        f", copy it over to `{_CONFIG_PATH}`, and restart the bot to apply your configuration"
    )


def _write_to_file(structured_data: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file_like:
        json.dump(structured_data, file_like, indent=2, ensure_ascii=False)


def _read_from_file(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file_like:
        return json.load(file_like)

# ==================================================
# Value Resolving
# ==================================================

def _resolve_dataclass_value(dataclass_type: type[DataclassT], data: Any, context: Context) -> DataclassT:
    """Resolve data to a dataclass instance.

    Returns:
        DataclassT: An instance of the dataclass_type.

    Raises:
        ConfigLoaderFieldException: If a dataclass field could not be resolved and config loading mode is STRICT.
        Exception: Any exception that might happen while trying to resolve unexpected data to a dataclass type
    """
    resolved_values: dict[str, Any] = {}

    for field in fields(dataclass_type):
        pushed_context = context.push_key(field.name)

        if field.name in data:
            try:
                resolved_values[field.name] = _resolve_value(field.type, data[field.name], pushed_context)
                continue

            # Let field exception bubble up so context at failure is preserved
            except ConfigLoaderFieldException:
                raise

            except ResolveValueError as resolveErr:
                _log_error_with_context(resolveErr, pushed_context)
            except Exception as e:
                _log_error_with_context(
                    ResolveValueError(pushed_context, field.type, data[field.name], f"{str(e)}"),
                    pushed_context
                )

        elif not is_optional_type(field.type):
            _log_error_with_context(
                ResolveValueError(pushed_context, field.type, None, "Missing data at path"),
                pushed_context
            )

        if pushed_context.loading_mode is ConfigLoadingMode.TEMPLATE:
            resolved_values[field.name] = _get_dataclass_field_template_value(field, dataclass_type, data, pushed_context)
            continue

        try:
            resolved_values[field.name] = _get_dataclass_field_default_value(field, dataclass_type, pushed_context)

        except UnresolvedAndDefaultValueMissingError as defaultErr:
            _log_error_with_context(defaultErr, pushed_context)

            assert pushed_context.loading_mode is not ConfigLoadingMode.TEMPLATE
            match pushed_context.loading_mode:
                case ConfigLoadingMode.LENIENT:
                    resolved_values[field.name] = _get_dataclass_field_lenient_value(field, data, pushed_context)
                case _: # STRICT
                    raise ConfigLoaderFieldException(defaultErr.context)

    return dataclass_type(**resolved_values)


def _resolve_value(type_: type, data: Any, context: Context) -> Any:
    """Resolve data to a typed value.

    Explicitly supported types:
        - Built-in 'primitives': int, float, str, bool
        - Built-in collections: dict, list, tuple, set
        - Unions: Union, shorthand X | Y, Optional
        - Dataclasses

    Raises:
        ResolveValueError: If a value cannot be resolved for every type in a Union
        Exception: Any exception that might happen while trying to resolve unexpected data to a type
    """
    if type_ is Any:
        return data

    elif is_optional_type(type_):
        if data is None:
            return None
        unwrapped_optional_type = unwrap_optional_type(type_)
        return _resolve_value(unwrapped_optional_type, data, context)

    # Try resolving left to right and return first match, simple but works
    elif is_union_type(type_):
        union_resolve_errors: list[Exception] = []
        for type_arg in get_args(type_):
            try:
                return _resolve_value(type_arg, data, context)
            except Exception as e:
                union_resolve_errors.append(e)
        error_reason = ", ".join(f"Error for type {_stringify_type(type_)}: {str(e)}" for e in union_resolve_errors)
        raise ResolveValueError(context, type_, data, error_reason)

    elif is_dataclass(type_):
        return _resolve_dataclass_value(type_, data, context)

    elif is_instantiable_dict_type(type_):
        type_args: tuple[Any, ...] = try_get_type_arguments(type_, (Any, Any))
        return dict(
            (
                _resolve_value(type_args[0], key, context.append_index(key)),
                _resolve_value(type_args[1], value, context.append_index(key))
            )
            for key, value in data.items()
        )

    elif is_instantiable_list_type(type_):
        type_arg: Any = try_get_type_arguments(type_, (Any,))[0]
        return list(
            _resolve_value(type_arg, item, context.append_index(index))
            for index, item in enumerate(data)
        )

    elif is_instantiable_tuple_type(type_):
        type_args: tuple[Any, ...] = try_get_type_arguments(type_, ())
        if len(type_args) == 2 and type_args[1] is Ellipsis:
            return tuple(
                _resolve_value(type_args[0], item, context.append_index(index))
                for index, item in enumerate(data)
            )
        elif len(type_args) >= 1:
            return tuple(
                _resolve_value(type_arg, data[index], context.append_index(index))
                for index, type_arg in enumerate(type_args)
            )
        return tuple(data)

    elif is_instantiable_set_type(type_):
        type_arg: Any = try_get_type_arguments(type_, (Any,))[0]
        return set(
            _resolve_value(type_arg, item, context)
            for item in data
        )

    elif type_ is bool:
        return convert_string_to_bool(data) if isinstance(data, str) else bool(data)

    else:
        return type_(data)

# ==================================================
# Value Loading by Dataclass Field
# ==================================================

def _get_dataclass_field_default_value(field: Field[Any], dataclass_type: type[DataclassT], context: Context) -> Any:
    """Get the default value of a dataclass field.

    Returns:
        Any: The dataclass field default value or None if the type is an Optional or Any.

    Raises:
        UnresolvedAndDefaultValueMissingError: If no default value can be returned.
    """
    if field.default is not MISSING:
        return field.default

    elif field.default_factory is not MISSING:
        return field.default_factory()

    elif is_optional_type(field.type) or field.type is Any:
        return None

    else:
        raise UnresolvedAndDefaultValueMissingError(context, field, dataclass_type)


def _get_dataclass_field_lenient_value(field: Field[Any], data: Any, context: Context) -> Any:
    """Resolve a dataclass for LENIENT config loading mode or get an empty-like value depending on type.

    Force LENIENT config loading mode.

    Returns:
        Any: A dataclass instance, an empty collection if instantiable or None regardless of type.
    """
    if is_dataclass(field.type):
        return _resolve_dataclass_value(field.type, data, context.force_loading_mode(ConfigLoadingMode.LENIENT))

    elif is_instantiable_collection_type(field.type):
         return field.type()

    return None


def _get_dataclass_field_template_value(
        field: Field[Any],
        dataclass_type: type[DataclassT],
        data: Any,
        context: Context
) -> Any:
    """Resolve a dataclass for TEMPLATE config loading mode or get a template value.

    Force TEMPLATE config loading mode.

    A template value is an info string signaling that this field could not be loaded, including:
        - A dataclass field default value if present
        - Field documentation if present in the field's metadata
        - One or more example values if present in the field's metadata.

    Returns:
        Any: A dataclass instance or a template value.
    """
    if is_dataclass(field.type):
        return _resolve_dataclass_value(field.type, data, context.force_loading_mode(ConfigLoadingMode.TEMPLATE))

    try:
        default_value = _get_dataclass_field_default_value(field, dataclass_type, context)
    except UnresolvedAndDefaultValueMissingError:
        default_value = MISSING

    metadata = _get_field_metadata(field)
    return (
        f"EXPECTING VALUE OF TYPE '{_stringify_type(field.type)}'"
        f"{", Default: "+repr(default_value) if default_value is not MISSING else ""}"
        f"{", Info: "+metadata["doc"] if metadata["doc"] else ""}"
        f"{(", Example: "+metadata["example"]) if metadata["example"] else ""}"
    )

# ==================================================
# Helpers
# ==================================================

def _log_error_with_context(obj: object, context: Context) -> None:
    """Log an error depending on context by using the contexts provided contextual logger.

    Use the default contextual logger if context does not provide one.
    """
    contextual_logger = context.contextual_logger if context.contextual_logger else _default_contextual_logger
    contextual_logger(obj, context)


def _default_contextual_logger(obj: object, context: Context) -> None:
    """Log an error as a warning except when config loading mode is TEMPLATE."""
    if context.loading_mode is not ConfigLoadingMode.TEMPLATE:
        log.warning(obj)


def _get_field_metadata(field: Field[Any]) -> dict[Any, Any]:
    """Helper to get a map of all supported metadata for a dataclass field.

    If a metadata key is not set it will be included with a None value.
    """
    metadata: dict[Any, Any] = {}

    for metadata_key in ("doc", "example"):
        try:
            metadata[metadata_key] = field.metadata[metadata_key]
        except KeyError:
            metadata[metadata_key] = None

    return metadata


def _stringify_type(type_: type) -> str:
    """Helper to get the name of a class if the type is a class or a string representation of the type."""
    if inspect.isclass(type_):
        return type_.__name__
    return str(type_)
