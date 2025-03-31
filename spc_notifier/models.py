from dataclasses import dataclass, field


@dataclass
class SpcProduct:
    title: str
    summary: str
    link: str


@dataclass
class TermFilters:
    title_must_include_one: list[str] = field(default_factory=list)
    title_must_exclude_all: list[str] = field(default_factory=list)
    summary_must_include_one: list[str] = field(default_factory=list)
    summary_must_exclude_all: list[str] = field(default_factory=list)


@dataclass
class WebhookConfig:
    url: str
    ping_user_or_role_id: str = ""
    filters: TermFilters = field(default_factory=TermFilters())
