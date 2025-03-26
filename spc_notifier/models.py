from typing import NamedTuple


class SpcProduct(NamedTuple):
    title: str
    summary: str
    link: str


class WebhookConfig(NamedTuple):
    url: str
    ping_user_or_role_id: str
    title_must_include: list[str]
    title_must_not_include: list[str]
    summary_must_include: list[str]
    summary_must_not_include: list[str]
