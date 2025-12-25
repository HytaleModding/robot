from dataclasses import dataclass

@dataclass(frozen=True)
class CoreConfig:
    guild_id: int | None

@dataclass(frozen=True)
class AutoThreadCogConfig:
    showcase_channel_id: int | None

@dataclass(frozen=True)
class AutoModCogConfig:
    whitelisted_role_ids: list[int]

@dataclass(frozen=True)
class GHIssuesCogConfig:
    known_repos: dict[str, str]
    status_emojis: dict[str, str]

@dataclass(frozen=True)
class LanguagesCogConfig:
    translator_channel_id: int | None
    languages: list[str]
    proof_reader_user_ids: dict[str, list[int]]
    thread_watcher_user_ids: list[int]

@dataclass(frozen=True)
class ModCogConfig:
    rules: list[str]

@dataclass(frozen=True)
class Tag:
    title: str | None
    description: str | None
    url: str | None

@dataclass(frozen=True)
class TagsCogConfig:
    tags: dict[str, Tag]
    test: dict[str, int]

@dataclass(frozen=True)
class TicketsCogConfig:
    logs_channel_id: int | None
    website_upload_url: str | None
    website_view_url: str | None
    staff_role_id: int | None

@dataclass(frozen=True)
class UtilsCogConfig:
    website_channel_id: int | None
    admin_role_id: int | None
    github_channel_id: int | None

@dataclass(frozen=True)
class CogsConfig:
    auto_thread: AutoThreadCogConfig
    automod: AutoModCogConfig
    gh_issues: GHIssuesCogConfig
    languages: LanguagesCogConfig
    mod: ModCogConfig
    tags: TagsCogConfig
    tickets: TicketsCogConfig
    utils: UtilsCogConfig

@dataclass(frozen=True)
class BotConfig:
    core: CoreConfig
    cogs: CogsConfig