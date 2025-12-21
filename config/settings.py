import logging
from dataclasses import dataclass

from config.env_var_loader import EnvVarLoader

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class BotSettings:
    TOKEN: str
    """str: Discord bot token
    """

    DB_HOST: str
    DB_PORT: int
    DB_USER: str | None
    DB_PASSWORD: str
    DB_NAME: str | None

    UPLOAD_TOKEN: str | None
    """str | None: Token for uploading ticket transcripts
    """

class Settings:
    _settings_instance: BotSettings | None = None

    @classmethod
    def init(cls) -> None:
        """Initialize settings. Should be called once during startup.

        Calling it multiple times has no effect.
        """
        if cls._settings_instance is not None:
            return

        cls._settings_instance = BotSettings(
            TOKEN=EnvVarLoader.get_required("TOKEN", str),

            DB_HOST=EnvVarLoader.get_required("DB_HOST", str, default_value="localhost"),
            DB_PORT=EnvVarLoader.get_required("DB_PORT", int, default_value=3306),
            DB_USER=EnvVarLoader.get_optional("DB_USER", str, default_value="root"),
            DB_PASSWORD=EnvVarLoader.get_required("DB_PASSWORD", str, default_value=""),
            DB_NAME=EnvVarLoader.get_optional("DB_NAME", str, default_value="moderation"),

            UPLOAD_TOKEN=EnvVarLoader.get_optional("UPLOAD_TOKEN", str)
        )

        log.info(f"Loaded settings")
        return

    @classmethod
    def get(cls) -> BotSettings:
        if cls._settings_instance is None:
            raise RuntimeError("Settings not initialized. Call Settings.init() first.")

        return cls._settings_instance