import re
import sys
sys.path.insert(0, r'C:\Users\Хозяин\Desktop\Farm\src')
from content_validator import (
    check_html_integrity, check_completeness, check_sentence_completeness,
    fix_truncated_html, fix_bold_stacking, extract_clean_text, validate_and_fix
)

print('=== Q1: fix_bold_stacking variants ===')
variants = [
    ('</b>\n<b>',        'newline between tags'),
    ('</b> <b>\n',       'space between, nl after <b>'),
    ('</b><b>',          'no whitespace'),
    ('</b> <b>',         'space between'),
    ('</b>\n\n<b>',      'double newline between'),
    ('</b> \n<b>',       'space+nl between tags'),
    ('</b>  <b>\n',      'double space, nl after <b>'),
    ('</b> <b> \n',      'spaces both sides, nl after <b>'),
]
for v, desc in variants:
    result = fix_bold_stacking(v)
    changed = result != v
    print('  [{}] {}: {!r} -> {!r}'.format('OK' if changed else 'UNCHANGED', desc, v, result))

print()
print('=== Q2: fix_truncated_html mid-word ===')
cases = [
    'Это текст, который обрывается на сло',
    'Привет мир. Это текст, которы',
    'Привет мир. Это. Текст, который обрывается',
    'Слово без точки',
    'Текст с многоточием… но не конец',
]
for c in cases:
    result = fix_truncated_html(c)
    changed = result != c
    print('  input: {!r}'.format(c))
    print('  output: {!r}  ({})'.format(result, 'CHANGED' if changed else 'UNCHANGED'))
    print()

print('=== Q5: self-closing tags in check_html_integrity ===')
test_cases = [
    '<p>Hello<br/>World</p>',
    '<p>Hello<img src="x.jpg" />World</p>',
    '<p>Hello<br>World</p>',
    '<div><br/><br/></div>',
    '<div><img src="x"/><br/></div>',
]
for tc in test_cases:
    ok, issues = check_html_integrity(tc)
    print('  {!r}: ok={}, issues={}'.format(tc, ok, issues))

print()
print('=== Q3: validate_and_fix fall-through ===')
# Case A: HTML fine, text truncated mid-word
print('Case A: HTML fine, text truncated mid-word')
html_a = '<p>Привет мир. Это текст который оборван на сло</p>'
result_a, issues_a = validate_and_fix(html_a, max_chars=2000)
print('  input: {!r}'.format(html_a))
print('  output: {!r}'.format(result_a))
print('  issues: {!r}'.format(issues_a))
print('  fixed? {}'.format('оборван' not in extract_clean_text(result_a)))
print()

# Case B: Text fine, HTML unclosed
print('Case B: Text fine, HTML unclosed')
html_b = '<p>Привет мир. Это текст.<b> Полный текст.</p>'
result_b, issues_b = validate_and_fix(html_b, max_chars=2000)
print('  input: {!r}'.format(html_b))
print('  output: {!r}'.format(result_b))
print('  issues: {!r}'.format(issues_b))
print()

# Case C: Both broken
print('Case C: Both broken')
html_c = '<p>Привет мир. Это текст.<b> Который оборван на сло'
result_c, issues_c = validate_and_fix(html_c, max_chars=2000)
print('  input: {!r}'.format(html_c))
print('  output: {!r}'.format(result_c))
print('  issues: {!r}'.format(issues_c))
print('  fixed truncation? {}'.format('Который оборван на сло' not in extract_clean_text(result_c)))
print()

# Case D: Length exceeded
print('Case D: Length exceeded')
html_d = '<p>Короткий текст.</p>'
result_d, issues_d = validate_and_fix(html_d, max_chars=20)
print('  input: {!r}'.format(html_d))
print('  output: {!r}'.format(result_d))
print('  issues: {!r}'.format(issues_d))
print()

print('=== Q2b: fix_truncated_html sentence boundary edge ===')
c = 'Полный текст. Обрыв сло'
print('  input: {!r}'.format(c))
print('  output: {!r}'.format(fix_truncated_html(c)))
print()

# Test fix_truncated_html on GOOD text (when called due to HTML issues)
print('=== fix_truncated_html ON GOOD TEXT (unclosed tags scenario) ===')
html_good = '<p>Привет мир. Это полный текст.</p>'
print('  input: {!r}'.format(html_good))
print('  output: {!r}'.format(fix_truncated_html(html_good)))
print()

html_good2 = '<b>Привет мир.</b> <b>Это полный текст.</b>'
print('  input: {!r}'.format(html_good2))
print('  output: {!r}'.format(fix_truncated_html(html_good2)))
print()

print('=== Q6: Validator says OK but text broken? ===')
# HTML entities case
html_entity = '<p>Hello world.&nbsp;</p>'
print('  HTML entities: {!r}'.format(html_entity))
result_e, issues_e = validate_and_fix(html_entity, max_chars=2000)
print('  output: {!r}'.format(result_e))
print('  text: {!r}'.format(extract_clean_text(result_e)))
print('  issues: {!r}'.format(issues_e))
print()

# Text ending with ellipsis + partial word
html_ellipsis = '<p>Привет мир… обрыв сло</p>'
print('  Ellipsis truncation: {!r}'.format(html_ellipsis))
result_f, issues_f = validate_and_fix(html_ellipsis, max_chars=2000)
print('  output: {!r}'.format(result_f))
print('  text: {!r}'.format(extract_clean_text(result_f)))
print('  issues: {!r}'.format(issues_f))
print('  fixed? {}'.format('обрыв' not in extract_clean_text(result_f)))
