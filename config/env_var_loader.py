import logging
import os
from typing import TypeVar, Type

from dotenv import load_dotenv

log = logging.getLogger(__name__)

EVT = TypeVar("EVT", str, int, bool)

class MissingRequiredEnvVarException(Exception):
    pass

class EnvVarLoader:
    _dotenv_loaded: bool = False

    @classmethod
    def _ensure_dotenv_loaded(cls) -> None:
        if cls._dotenv_loaded:
            return

        load_dotenv()
        cls._dotenv_loaded = True

    @classmethod
    def get_optional(cls, key: str, target_type: Type[EVT], *,
                     default_value: EVT | None = None) -> EVT | None:
        """Get a typed environment variable or None.

        Args:
            key (str): The name of the environment variable.
            target_type (Type[EVT]): The type the value will be converted to.
            default_value (EVT | None): The value to use if the environment variable is not set. Defaults to None.

        Returns:
            EVT | None: The value of the environment variable with the provided target type if set
            or the default value if provided, otherwise None.
        """
        env_variable: EVT | None = cls._resolve(key, target_type, True, default_value)

        if env_variable is None:
            log.warning(f"Optional environment variable \"{key}\" is not set, some features might not work")
            return None

        return env_variable

    @classmethod
    def get_required(cls, key: str, target_type: Type[EVT], *,
                     default_value: EVT | None = None) -> EVT:
        """Get a typed environment variable.

        Args:
            key (str): The name of the environment variable.
            target_type (Type[EVT]): The type the value will be converted to.
            default_value (EVT | None): The value to use if the environment variable is not set. Defaults to None.

        Returns:
            EVT: The value of the environment variable with the provided target type.

        Raises:
            MissingRequiredEnvVarException: If the required environment variable is not set.
        """
        env_variable: EVT | None = cls._resolve(key, target_type, True, default_value)

        if env_variable is None:
            raise MissingRequiredEnvVarException(f"Required environment variable \"{key}\" is not set")

        return env_variable

    @classmethod
    def _resolve(cls, key: str, target_type: Type[EVT], required: bool,
                 default_value: EVT | None) -> EVT | None:
        """Resolve an environment variable into a typed value.

        Lazy load dotenv, read the environment variable, and convert it to `target_type` if it is set,
        otherwise fall back to `default_value` or None.

        This function does not enforce whether an environment variable is required or not,
        `required` is only used for logging.

        Args:
            key (str): The name of the environment variable.
            target_type (Type[EVT]): The type the value will be converted to.
            required (bool): Whether the variable is considered required.
                Used only for logging purposes.
            default_value (EVT | None): The value to use if the environment variable is not set.

        Returns:
            EVT | None: The value of the environment variable with the provided target type if set
            or the default value if provided, otherwise None.
        """
        cls._ensure_dotenv_loaded()

        loaded_env_value: str | None = os.getenv(key)

        # Empty string is not a valid value for `loaded_env_value`
        if loaded_env_value:
            return cls._convert_env_value(loaded_env_value, target_type)

        # Empty string is a valid value for `default_value`
        if default_value is not None:
            log.warning(f"{"Required" if required else "Optional"} environment variable \"{key}\" is not set"
                        f", using default value \"{default_value}\" instead")
            return target_type(default_value)
        else:
            return None

    @staticmethod
    def _convert_env_value(value: str, target_type: Type[EVT]) -> EVT:
        if target_type is str:
            return str(value)
        elif target_type is int:
            return int(value)
        elif target_type is bool:
            return EnvVarLoader._str_to_bool(value)
        else:
            raise TypeError(f"Unsupported type \"{target_type}\" for typecasting env value \"{value}\"")

    @staticmethod
    def _str_to_bool(value: str) -> bool:
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        elif value.lower() in ("false", "no", "0", "off"):
            return False
        else:
            raise ValueError(f"Invalid literal for string to bool conversion: \"{value}\"")