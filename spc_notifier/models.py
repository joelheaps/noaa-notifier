from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self, TypedDict

import structlog

logger = structlog.get_logger(__name__)


class SpcProduct(TypedDict):
    title: str
    summary: str
    link: str
    seen_at: datetime = datetime.now(tz=UTC)


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

    @classmethod
    def from_dict(cls, dict_: dict) -> Self:
        """Convert nested filter config into TermFilters object before returning WebhookConfig"""
        dict_["filters"] = TermFilters(**dict_.get("filters", {}))
        return WebhookConfig(**dict_)


@dataclass
class LLMConfig:
    enable_llm_summaries: bool = False
    include_spc_summaries: bool = True
    claude_api_key: str = ""
    claude_model: str = ""
    claude_max_tokens: int = 1024
    prompt: str = ""

    def __post_init__(self) -> None:
        if not self.enable_llm_summaries and not self.include_spc_summaries:
            logger.warning(
                "Both 'enable_llm_summaries' and 'include_spc_summaries' were disabled. Enabling 'include_spc_summaries' so messages aren't empty."
            )
            self.include_spc_summaries = True
