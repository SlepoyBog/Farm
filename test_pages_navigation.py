import unittest
from urllib.parse import urljoin

from src.site_generator import HEAD, ARTICLE_TEMPLATE, CSS


class PagesNavigationTests(unittest.TestCase):
    def test_templates_keep_project_prefix(self):
        import re
        for template in (HEAD, ARTICLE_TEMPLATE):
            for link in re.findall(r'href="([^"]+)"', template):
                if link.startswith('./'):
                    self.assertTrue(urljoin('https://example.org/Farm/article.html', link)
                                    .startswith('https://example.org/Farm/'))
                self.assertFalse(link.startswith('/'), link)

    def test_header_can_grow_and_wrap(self):
        self.assertIn('min-height:60px', CSS)
        self.assertNotIn(';height:60px', CSS)
        self.assertIn('top:100%;left:0;right:0;', CSS)


if __name__ == '__main__':
    unittest.main()

