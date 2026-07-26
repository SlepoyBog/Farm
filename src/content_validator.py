import logging
import re

logger = logging.getLogger(__name__)

VOID_ELEMENTS = {
    "br", "hr", "img", "input", "meta", "link",
    "area", "base", "col", "embed", "source", "track", "wbr",
}

SENTENCE_ENDERS = {".", "!", "?", "\u2026", '"', "\u00bb", ")"}
SENTENCE_ENDERS_PATTERN = r"(?<=[.!?\u2026\"\u00bb)])\s+"
TRUNCATED_FRAGMENT_MAX_LEN = 3


def check_html_integrity(html: str) -> tuple[bool, list[str]]:
    issues = []

    if not html or not html.strip():
        return False, ["Empty content"]

    open_tags = []
    i = 0
    while i < len(html):
        if html[i] == "<":
            end = html.find(">", i)
            if end == -1:
                issues.append("Unclosed '<' at position %d" % i)
                break
            tag_content = html[i + 1 : end].strip()
            if tag_content.startswith("/"):
                tag_name = tag_content[1:].split()[0]
                if open_tags and open_tags[-1] == tag_name:
                    open_tags.pop()
                else:
                    issues.append("Unexpected closing tag </%s>" % tag_name)
            elif tag_content.endswith("/"):
                pass
            elif tag_content.startswith("!--"):
                i = end + 1
                continue
            elif tag_content.startswith("?"):
                i = end + 1
                continue
            else:
                tag_name = tag_content.split()[0].split(">")[0]
                if tag_name.lower() not in VOID_ELEMENTS:
                    open_tags.append(tag_name)
            i = end + 1
        else:
            i += 1

    if open_tags:
        issues.append("Unclosed tags: %s" % ", ".join(open_tags))

    return len(issues) == 0, issues


def check_completeness(text: str) -> tuple[bool, str | None]:
    import html as html_module
    stripped = html_module.unescape(text).rstrip()
    if not stripped:
        return False, "Empty text"

    last_char = stripped[-1]
    if last_char in SENTENCE_ENDERS:
        return True, None

    sentence_boundary = re.search(r'[.!?\u2026]["\u00bb)]?\s+', stripped)
    incomplete_word = stripped.rsplit(maxsplit=1)[-1]
    if (
        sentence_boundary
        and incomplete_word.isalpha()
        and len(incomplete_word) <= TRUNCATED_FRAGMENT_MAX_LEN
    ):
        return False, "Text truncated: incomplete word '%s...'" % incomplete_word

    return True, None


def check_sentence_completeness(text: str) -> bool:
    complete, _ = check_completeness(re.sub(r"<[^>]+>", "", text))
    return complete


def _close_open_tags(html: str) -> str:
    """Балансирует простой сгенерированный HTML, сохраняя текст."""
    result: list[str] = []
    open_tags: list[str] = []
    cursor = 0

    for match in re.finditer(r"<!--.*?-->|<[^>]*>", html, flags=re.DOTALL):
        result.append(html[cursor:match.start()])
        token = match.group(0)
        raw = token[1:-1].strip()
        cursor = match.end()

        if token.startswith("<!--") or raw.startswith(("!", "?")):
            result.append(token)
            continue

        if raw.startswith("/"):
            tag_name = raw[1:].split()[0].lower()
            if tag_name not in open_tags:
                continue
            while open_tags and open_tags[-1] != tag_name:
                result.append("</%s>" % open_tags.pop())
            open_tags.pop()
            result.append(token)
            continue

        result.append(token)
        if not raw.endswith("/"):
            tag_name = raw.split()[0].lower()
            if tag_name not in VOID_ELEMENTS:
                open_tags.append(tag_name)

    result.append(html[cursor:])
    result.extend("</%s>" % tag for tag in reversed(open_tags))
    return "".join(result)


def fix_truncated_html(html: str) -> str:
    stripped = html.rstrip()
    if not stripped:
        return html

    boundaries = list(
        re.finditer(r'[.!?\u2026](?:["\u00bb)])?(?=\s|<|$)', stripped)
    )
    if boundaries:
        html = stripped[:boundaries[-1].end()]

    return _close_open_tags(html)


def fix_bold_stacking(html: str) -> str:
    html = re.sub(r'</b>\s*<b>\s*\n\s*', '</b>\n<b>', html)
    html = re.sub(r'</b>\s*\n\s*<b>\s*', '</b>\n<b>', html)
    return html


def strip_markdown_fences(text: str) -> str:
    text = re.sub(r'`{3,}(?:html)?\s*|\s*`{3,}', '', text)
    text = re.sub(r'~{3,}(?:html)?\s*|\s*~{3,}', '', text)
    return text


def extract_clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    import html as html_module
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def validate_and_fix(
    html: str,
    max_chars: int = 950,
    context: str = "content",
) -> tuple[str, list[str]]:
    issues = []
    original = html

    html = strip_markdown_fences(html)
    html = fix_bold_stacking(html)

    html_ok, html_issues = check_html_integrity(html)
    if not html_ok:
        for iss in html_issues:
            logger.warning("[%s] HTML issue: %s", context, iss)
            issues.append(iss)
        html = _close_open_tags(html)
        issues.append("Fixed HTML structure")

    text = extract_clean_text(html)
    complete_ok, complete_issue = check_completeness(text)
    sentences_ok = check_sentence_completeness(text)

    if not complete_ok or not sentences_ok:
        if complete_issue:
            logger.warning('[%s] %s', context, complete_issue)
            issues.append(complete_issue)
        html = fix_truncated_html(html)
        issues.append("Fixed truncated ending")

    if len(html) > max_chars:
        TRUNCATION_SAFETY = 50
        threshold = max_chars - TRUNCATION_SAFETY
        if threshold > 200:
            logger.warning("[%s] Length %d > %d — truncating", context, len(html), max_chars)
            trimmed = html[:threshold]
            html = fix_truncated_html(trimmed)
            issues.append("Truncated to %d chars" % max_chars)

    html_ok, _ = check_html_integrity(html)
    if not html_ok:
        html = _close_open_tags(html)
        if "Fixed HTML after truncation" not in issues:
            issues.append("Fixed HTML after truncation")

    if issues:
        logger.info("[%s] Fixed %d issue(s)", context, len(issues))

    return html, issues
