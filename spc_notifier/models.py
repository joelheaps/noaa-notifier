from typing import NamedTuple


class SpcProduct(NamedTuple):
    title: str
    summary: str
    link: str


class TermFilters(NamedTuple):
    title_must_include_one: list[str] = list
    title_must_exclude_all: list[str] = list
    summary_must_include_one: list[str] = list
    summary_must_exclude_all: list[str] = list


class WebhookConfig(NamedTuple):
    url: str
    ping_user_or_role_id: str = ""
    filters: TermFilters = TermFilters()
