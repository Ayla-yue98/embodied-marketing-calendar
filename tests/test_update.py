import unittest
from datetime import date
from unittest.mock import patch
import update

class DateSafety(unittest.TestCase):
    def test_chinese_and_international_dates(self):
        self.assertEqual(update.parse_date('2026年10月28日'),date(2026,10,28))
        self.assertEqual(update.parse_date('October 28, 2026'),date(2026,10,28))
        self.assertIsNone(update.parse_date('© 2026; no dated article'))
        self.assertIsNone(update.parse_date('2026-02-30'))

    def test_modified_date_does_not_become_publication(self):
        p=update.Page();p.feed('<script type="application/ld+json">{"@type":"WebPage","dateModified":"2026-11-06"}</script>')
        self.assertIsNone(update.published(p))
        p=update.Page();p.feed('<script type="application/ld+json">{"@graph":[{"@type":"NewsArticle","datePublished":"2026-10-28T10:30:00+08:00","dateModified":"2026-11-06"}]}</script>')
        self.assertEqual(update.published(p),date(2026,10,28))

    def test_future_articles_are_excluded_and_duplicates_collapsed(self):
        p=update.Page();p.feed('<a href="/news/1">Product launch 2026-10-28</a><a href="/news/1">Product launch 2026-10-28</a><a href="/news/2">Future launch 2026-12-01</a>')
        source={'company':'unitree','url':'https://example.com/news','allowed_hosts':['example.com'],'article_pattern':'/news/[0-9]+','publisher':'Official'}
        with patch('update.fetch',return_value=(p,source['url'])):
            events,report=update.collect(source,date(2026,10,1),date(2026,11,6))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['date_basis'],'publication')
        self.assertEqual(events[0]['status'],'collected')
        self.assertEqual(report['skipped_future'],1)

    def test_unparseable_page_reports_failure(self):
        p=update.Page();p.feed('<h1>Client-rendered news</h1>')
        source={'company':'unitree','url':'https://example.com/news','allowed_hosts':['example.com'],'article_pattern':'/news/[0-9]+','publisher':'Official'}
        with patch('update.fetch',return_value=(p,source['url'])):
            events,report=update.collect(source,date(2026,10,1),date(2026,11,6))
        self.assertEqual(events,[])
        self.assertEqual(report['state'],'入口需维护')

    def test_undated_articles_do_not_report_empty_month_as_success(self):
        p=update.Page();p.feed('<a href="/news/1">Robot launch with no published date</a>')
        source={'company':'unitree','url':'https://example.com/news','allowed_hosts':['example.com'],'article_pattern':'/news/[0-9]+','publisher':'Official'}
        with patch('update.fetch',return_value=(p,source['url'])):
            events,report=update.collect(source,date(2026,10,1),date(2026,11,6))
        self.assertEqual(events,[])
        self.assertEqual(report['state'],'日期解析需维护')

if __name__=='__main__':unittest.main()
