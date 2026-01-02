from dataclasses import dataclass
from dataclasses import field as field_constructor


@dataclass(frozen=True)
class CoreConfig:
    """Contains options used by all cogs."""
    guild_id: int = field_constructor(
        metadata={"doc": "Guild ID. The guild for which the bot is supposed to run."}
    )


@dataclass(frozen=True)
class AutoThreadCogConfig:
    showcase_channel_id: int = field_constructor(
        metadata={"doc": "Channel ID. All messages in this channel will be handled by auto_thread cog."}
    )


@dataclass(frozen=True)
class AutoModCogConfig:
    whitelisted_role_ids: list[int] = field_constructor(
        default_factory=list,
        metadata={"doc": "List of role IDs. Users with listed roles will be exempt from handling by automod cog."}
    )


@dataclass(frozen=True)
class GHIssuesCogConfig:
    known_repos: dict[str, str] = field_constructor(
        default_factory=dict,
        metadata={
            "doc":
                "Map of repository names and repository identifiers."
                " Mapped repositories will be handled by gh_issues cog.",
            "example": "{'robot': 'hytalemodding/robot'}"
        }
    )
    # Maybe make this a dataclass instead since keys are not dynamic?
    status_emojis: dict[str, str] = field_constructor(
        default_factory=dict,
        metadata={
            "doc":
                "Map of repository actions and emojis or guild emojis."
                " Mapped emojis will be used for decorating mentioned repository actions.",
            "example": "{'issue_open': '<:IssueOpen:514>', 'commit': '📝'}"
        }
    )


@dataclass(frozen=True)
class LanguagesCogConfig:
    translator_channel_id: int = field_constructor(
        metadata={"doc": "Channel ID. Private language threads will be managed by languages cog in this channel."}
    )
    languages: list[str] = field_constructor(
        default_factory=list,
        metadata={
            "doc": "List of languages. Private threads will be managed by languages cog for listed languages.",
            "example": "['Arabic', 'German', 'Latvian']"
        }
    )
    proof_reader_user_ids_by_language: dict[str, list[int]] = field_constructor(
        default_factory=dict,
        metadata={
            "doc":
                "Map of languages and list of user IDs."
                " Mapped list of users with extra permissions in the private language thread managed by languages cog.",
            "example": "{'German': [123, 127], 'Latvian': [131]}"
        }
    )
    thread_watcher_user_ids: list[int] = field_constructor(
        default_factory=list,
        metadata={
            "doc":
                "List of user IDs."
                " Listed users get access to all private language threads managed by languages cog."
        }
    )


@dataclass(frozen=True)
class ModCogConfig:
    rules: list[str] = field_constructor(
        default_factory=list,
        metadata={"doc": "List of rules. Used for command option autocompletion in mod cog."}
    )


@dataclass(frozen=True)
class Tag:
    title: str | None
    description: str | None
    url: str | None


@dataclass(frozen=True)
class TagsCogConfig:
    mentionable_tags: dict[str, Tag] = field_constructor(
        default_factory=dict,
        metadata={
            "doc":
                "Map of tag names and a 'config.model.Tag'."
                " Mapped Tags will be handled by tags cog to send a reply based on mentioned tag name.",
            "example": "{'bot': {'url': 'https://github.com/HytaleModding/robot'}}"
        }
    )


@dataclass(frozen=True)
class TicketsCogConfig:
    staff_role_id: int = field_constructor(
        metadata={"doc": "Role ID. Users with this role have extra permissions for actions handled by tickets cog."}
    )
    logs_channel_id: int = field_constructor(
        metadata={"doc": "Channel ID. Various logs from tickets cog will be sent to this channel."}
    )
    website_upload_url: str | None = field_constructor(
        default=None,
        metadata={"doc": "URL. Ticket transcripts created by tickets cog will be sent to this URL."}
    )
    website_view_url: str | None = field_constructor(
        default=None,
        metadata={"doc": "URL. The view URL that is returned after uploading a ticket transcript."}
    )


@dataclass(frozen=True)
class UtilsCogConfig:
    website_project_channel_id: int = field_constructor(
        metadata={
            "doc":
                "Channel ID. A channel that gets treated as a thread for thread-specific actions handled by utils cog."
        }
    )
    admin_role_id: int = field_constructor(
        metadata={"doc": "Role ID. Users with this role have extra permissions for actions handled by utils cog."}
    )
    github_updates_channel_id: int = field_constructor(
        metadata={"doc": "Channel ID. A channel to exclude for certain actions handled by utils cog."}
    )
    profanity_filter_whitelist: list[str] = field_constructor(
        default_factory=list,
        metadata={"doc": "List of words. Words to exclude from the profanity filter wordlist used by utils cog."}
    )


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
class ConfigSchema:
    """Schema root for bot config.

    Supported metadata keys for fields:
        - 'doc': An short summary of what the config option is required for.
        - 'example': One or more example values.
    """
    core: CoreConfig
    cogs: CogsConfig
