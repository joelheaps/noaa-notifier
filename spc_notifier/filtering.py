import structlog

from spc_notifier.models import SpcProduct, TermFilters

logger = structlog.get_logger()


def check_contains_terms(terms: list[str] | None, string_: str) -> bool:
    """Check if string contains at least one of the terms provided.
    Returns True if terms is None or empty."""
    if not terms:
        return True
    string_ = string_.lower()
    return any(term.lower() in string_ for term in terms)


def check_passes_filters(
    product: SpcProduct,
    filters: TermFilters,
) -> bool:
    """Determines whether an entry contains wanted and unwanted terms."""
    filter_results = {
        "title_include": check_contains_terms(
            filters.title_must_include_one, product.title
        ),
        "title_exclude": not check_contains_terms(
            filters.title_must_exclude_all, product.title
        ),
        "summary_include": check_contains_terms(
            filters.summary_must_include_one, product.summary
        ),
        "summary_exclude": not check_contains_terms(
            filters.summary_must_exclude_all, product.summary
        ),
    }

    if all(filter_results.values()):
        return True

    logger.info(
        "Product did not pass filters.",
        product=product.title,
        title_must_include_one="pass" if filter_results["title_include"] else "fail",
        title_must_exclude_all="pass" if filter_results["title_exclude"] else "fail",
        summary_must_include_one="pass"
        if filter_results["summary_include"]
        else "fail",
        summary_must_exclude_all="pass"
        if filter_results["summary_exclude"]
        else "fail",
    )
    return False
