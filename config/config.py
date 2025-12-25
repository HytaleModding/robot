import logging

from .loader import load_config
from .model import BotConfig

log = logging.getLogger(__name__)

class Config:
    _config_instance: BotConfig | None = None

    @classmethod
    def init(cls) -> None:
        """Initialize config. Should be called once during startup.

        Calling it multiple times has no effect.
        """
        if cls._config_instance is not None:
            return

        cls._config_instance = load_config()

        log.info(f"Loaded config")
        return

    @classmethod
    def get(cls) -> BotConfig:
        if cls._config_instance is None:
            raise RuntimeError("Config not initialized. Call Config.init() first.")

        return cls._config_instance