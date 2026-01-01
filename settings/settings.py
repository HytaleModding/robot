import logging
from dataclasses import dataclass

from settings.env_var_loader import EnvVarLoader

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class SettingsSchema:
    TOKEN: str
    """str: Discord bot token"""

    DB_HOST: str
    DB_PORT: int
    DB_USER: str | None
    DB_PASSWORD: str
    DB_NAME: str | None

    UPLOAD_TOKEN: str | None
    """str | None: Token for uploading ticket transcripts"""

class Settings:
    _settings_instance: SettingsSchema | None = None

    @classmethod
    def init(cls) -> None:
        """Initialize settings. Should be called once during startup.

        Calling it multiple times has no effect.
        """
        if cls._settings_instance is not None:
            return

        cls._settings_instance = SettingsSchema(
            TOKEN=EnvVarLoader.get_required_str("TOKEN"),

            DB_HOST=EnvVarLoader.get_required_str("DB_HOST", default_value="localhost"),
            DB_PORT=EnvVarLoader.get_required_int("DB_PORT", default_value=3306),
            DB_USER=EnvVarLoader.get_optional_str("DB_USER", default_value="root"),
            DB_PASSWORD=EnvVarLoader.get_optional_str("DB_PASSWORD", default_value=""),
            DB_NAME=EnvVarLoader.get_optional_str("DB_NAME", default_value="moderation"),

            UPLOAD_TOKEN=EnvVarLoader.get_optional_str("UPLOAD_TOKEN")
        )

        log.info(f"Loaded settings")
        return

    @classmethod
    def get(cls) -> SettingsSchema:
        """Get settings instance.

        Raises:
            RuntimeError: If the settings instance is not initialized.
        """
        if cls._settings_instance is None:
            raise RuntimeError("Settings not initialized. Call Settings.init() first.")

        return cls._settings_instance
