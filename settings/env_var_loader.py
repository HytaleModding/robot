import logging
import os
from typing import TypeVar, cast

from dotenv import load_dotenv

from utils.typing_utils import convert_string_to_bool

log = logging.getLogger(__name__)

EVT = TypeVar("EVT", str, int, bool)

class EnvVarLoaderException(Exception):
    """This exception will be raised when the user provided environment variables lead to an error during loading.

    This may be due to a missing required environment variable without a default value, or an environment variable value that cannot be converted to the expected type.

    This should not be raised if there is an error due to invalid use of the loader in within the codebase.
    """
    pass

class EnvVarLoader:
    """Utility class for loading and validating typed environment variables for Settings.

    Optional environment variables that are missing without a default value return None with a warning.
    Required variables that are missing without a default value raise an exception.
    """
    _dotenv_loaded: bool = False

    @classmethod
    def _ensure_dotenv_loaded(cls) -> None:
        if cls._dotenv_loaded:
            return

        load_dotenv()
        cls._dotenv_loaded = True

    @classmethod
    def get_optional_str(cls, key: str, *, default_value: str | None = None) -> str | None:
        """Get an optional environment variable as a str."""
        return cls._get_optional(key, str, default_value)
    @classmethod
    def get_optional_int(cls, key: str, *, default_value: int | None = None) -> int | None:
        """Get an optional environment variable as an int."""
        return cls._get_optional(key, int, default_value)
    @classmethod
    def get_optional_bool(cls, key: str, *, default_value: bool | None = None) -> bool | None:
        """Get an optional environment variable as a bool."""
        return cls._get_optional(key, bool, default_value)
    @classmethod
    def _get_optional(cls, key: str, target_type: type[EVT], default_value: EVT | None) -> EVT | None:
        """Get a typed environment variable or None.

        Args:
            key (str): The name of the environment variable.
            target_type (type[EVT]): The type the value will be converted to.
            default_value (EVT | None): The value to use if the environment variable is not set. Defaults to None.

        Returns:
            EVT | None: The value of the environment variable with the provided target type if set or the default value if provided, otherwise None.
        """
        env_var: EVT | None = cls._resolve(key, target_type, default_value)

        if env_var is None:
            log.warning(f"Environment variable \"{key}\" is not set. Some features might not work")
            return None

        return env_var

    @classmethod
    def get_required_str(cls, key: str, *, default_value: str | None = None) -> str:
        """Get a required environment variable as a str."""
        return cls._get_required(key, str, default_value)
    @classmethod
    def get_required_int(cls, key: str, *, default_value: int | None = None) -> int:
        """Get a required environment variable as an int."""
        return cls._get_required(key, int, default_value)
    @classmethod
    def get_required_bool(cls, key: str, *, default_value: bool | None = None) -> bool:
        """Get a required environment variable as a bool."""
        # We know the returned value is a bool, but type-checker doesn't since bool is a subtype of int
        return cast(bool, cls._get_required(key, bool, default_value))
    @classmethod
    def _get_required(cls, key: str, target_type: type[EVT], default_value: EVT | None) -> EVT:
        """Get a typed environment variable.

        Args:
            key (str): The name of the environment variable.
            target_type (type[EVT]): The type the value will be converted to.
            default_value (EVT | None): The value to use if the environment variable is not set. Defaults to None.

        Returns:
            EVT: The value of the environment variable with the provided target type.

        Raises:
            EnvVarLoaderException: If the required environment variable is not set.
        """
        env_var: EVT | None = cls._resolve(key, target_type, default_value)

        if env_var is None:
            raise EnvVarLoaderException(f"Environment variable \"{key}\" is not set. It is required to run the bot")

        return env_var

    @classmethod
    def _resolve(cls, key: str, target_type: type[EVT], default_value: EVT | None) -> EVT | None:
        """Resolve an environment variable into a typed value.

        Lazy load dotenv, read the environment variable, and convert it to `target_type` if it is set,
        otherwise fall back to `default_value` or None.

        Args:
            key (str): The name of the environment variable.
            target_type (type[EVT]): The type the value will be converted to.
            default_value (EVT | None): The value to use if the environment variable is not set.

        Returns:
            EVT | None: The value of the environment variable with the provided target type if set or the default value if provided, otherwise None.

        Raises:
            EnvVarLoaderException: If the required environment variable is not set.
        """
        cls._ensure_dotenv_loaded()

        loaded_env_var_value: str | None = os.getenv(key)

        # Empty string for `loaded_env_var_value` is treated as a missing env var
        if loaded_env_var_value:
            try:
                return cls._convert_env_var_value(loaded_env_var_value, target_type)
            except ValueError as e:
                raise EnvVarLoaderException(
                    f"Environment variable \"{key}\" is expected to be of type \"{target_type}\""                     
                    f", but the provided value could not be converted: {e}"
                )

        # Empty string is a valid value for `default_value`
        if default_value is not None:
            log.warning(
                f"Environment variable \"{key}\" is not set"
                f", using default value \"{default_value}\" instead"
            )
            try:
                return target_type(default_value)
            except ValueError as e:
                raise ValueError(f"Type of default value does not match provided target type: {e}")
        else:
            return None

    @staticmethod
    def _convert_env_var_value(value: str, target_type: type[EVT]) -> EVT:
        if target_type is str:
            return str(value)

        elif target_type is int:
            return int(value)

        elif target_type is bool:
            return convert_string_to_bool(value)

        else:
            raise TypeError(f"Unsupported type \"{target_type}\" for converting env value string \"{value}\"")
