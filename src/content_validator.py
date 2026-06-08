import logging
import re

logger = logging.getLogger(__name__)


def check_html_integrity(html: str) -> tuple[bool, list[str]]:
    """Проверяет целостность HTML: закрыты ли все теги и нет ли битой разметки."""
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
                pass
            elif tag_content.startswith("?"):
                pass
            else:
                tag_name = tag_content.split()[0].split(">")[0]
                void_elements = {
                    "br", "hr", "img", "input", "meta", "link",
                    "area", "base", "col", "embed", "source", "track", "wbr",
                }
                if tag_name.lower() not in void_elements:
                    open_tags.append(tag_name)
            i = end + 1
        else:
            i += 1

    if open_tags:
        issues.append("Unclosed tags: %s" % ", ".join(open_tags))

    return len(issues) == 0, issues


def check_completeness(text: str) -> tuple[bool, str | None]:
    """Проверяет, не обрезан ли текст посередине предложения/слова."""
    stripped = text.rstrip()
    if not stripped:
        return False, "Empty text"

    sentence_enders = {".", "!", "?", "…", '"', "»", ")"}
    last_char = stripped[-1]

    if last_char in sentence_enders:
        return True, None

    last_space = stripped.rfind(" ")
    if last_space > len(stripped) // 2:
        incomplete_word = stripped[last_space + 1:]
        if incomplete_word and not incomplete_word[-1].isalpha():
            return True, None
        return False, "Text truncated: incomplete word '%s...'" % incomplete_word

    if last_char.isalpha():
        return False, "Text truncated: ends mid-word at '%s'" % stripped[-15:]

    return True, None


def check_sentence_completeness(text: str) -> bool:
    """Проверяет, что все предложения завершены (не обрываются на середине)."""
    stripped = text.rstrip()
    if not stripped:
        return False

    stripped = re.sub(r"<[^>]+>", "", stripped)
    sentences = re.split(r"(?<=[.!?])\s+", stripped)
    if not sentences:
        return False

    last_sentence = sentences[-1].strip()
    if len(last_sentence) < 3:
        return True

    sentence_enders = {".", "!", "?", "…", '"', "»", ")"}
    last_char = last_sentence[-1] if last_sentence else ""
    return last_char in sentence_enders


def fix_truncated_html(html: str) -> str:
    """Удаляет обрезанное содержимое в конце и закрывает теги."""
    stripped = html.rstrip()
    if not stripped:
        return html

    sentence_enders = {".", "!", "?", "…", '"', "»", ")"}
    last_good = 0

    for match in re.finditer(r"(?<=[.!?])\s+", stripped):
        pos = match.end()
        if pos > last_good:
            last_good = pos

    if last_good > 0:
        cut_pos = last_good
        while cut_pos < len(stripped) and stripped[cut_pos] in " \t\n\r":
            cut_pos += 1
        html = stripped[:cut_pos]
    else:
        html = stripped

    open_tags = []
    i = 0
    while i < len(html):
        if html[i] == "<":
            end = html.find(">", i)
            if end == -1:
                break
            tag = html[i + 1 : end].split()[0].split(">")[0]
            if not tag.startswith("/") and not tag.endswith("/"):
                void_elements = {
                    "br", "hr", "img", "input", "meta", "link", "area",
                    "base", "col", "embed", "source", "track", "wbr",
                }
                if tag.lower() not in void_elements:
                    open_tags.append(tag)
            elif tag.startswith("/") and open_tags:
                open_tags.pop()
            i = end + 1
        else:
            i += 1

    for tag in reversed(open_tags):
        html += "</%s>" % tag

    return html


def extract_clean_text(html: str) -> str:
    """Извлекает чистый текст из HTML."""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def validate_and_fix(
    html: str,
    max_chars: int = 950,
    context: str = "content",
) -> tuple[str, list[str]]:
    """Полная валидация: HTML, обрывы, длина. Возвращает (исправленный html, список проблем)."""
    issues = []
    original = html

    html_ok, html_issues = check_html_integrity(html)
    if not html_ok:
        for iss in html_issues:
            logger.warning("[%s] HTML issue: %s", context, iss)
            issues.append(iss)

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
        HTML_TRUNCATION_SAFETY = 50
        threshold = max_chars - HTML_TRUNCATION_SAFETY
        if threshold > 200:
            logger.warning("[%s] Length %d > %d — truncating", context, len(html), max_chars)
            html = fix_truncated_html(html[:threshold])
            issues.append("Truncated to %d chars" % max_chars)

    html_ok, _ = check_html_integrity(html)
    if not html_ok:
        html = fix_truncated_html(html)
        if "Fixed HTML after truncation" not in issues:
            issues.append("Fixed HTML after truncation")

    if issues:
        logger.info("[%s] Fixed %d issue(s)", context, len(issues))

    return html, issues
