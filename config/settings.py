import logging
from typing import Optional

from config.env_var_loader import EnvVarLoader, MissingRequiredEnvVarException

log = logging.getLogger(__name__)

class Settings:
    TOKEN: str
    """str: Discord bot token
    """

    DB_HOST: str
    DB_PORT: int
    DB_USER: Optional[str]
    DB_PASSWORD: str
    DB_NAME: Optional[str]

    UPLOAD_TOKEN: Optional[str]
    """Optional[str]: Token for uploading ticket transcripts
    """

    _loaded: bool = False

    @classmethod
    def load(cls) -> None:
        """Load environment variables into class attributes.

        Calling it multiple times has no effect.

        Raises:
            MissingRequiredEnvVarException: If a required environment variable is not set.
        """
        if cls._loaded:
            return

        try:
            cls.TOKEN = EnvVarLoader.get_required("TOKEN", str)

            cls.DB_HOST = EnvVarLoader.get_required("DB_HOST", str, default_value="localhost")
            cls.DB_PORT = EnvVarLoader.get_required("DB_PORT", int, default_value=3306)
            cls.DB_USER = EnvVarLoader.get_optional("DB_USER", str)
            cls.DB_PASSWORD = EnvVarLoader.get_required("DB_PASSWORD", str, default_value="")
            cls.DB_NAME = EnvVarLoader.get_optional("DB_NAME", str)

            cls.UPLOAD_TOKEN = EnvVarLoader.get_optional("UPLOAD_TOKEN", str)
        except MissingRequiredEnvVarException:
            raise

        log.info(f"Loaded settings")
        cls._loaded = True