import unittest

from fanfic2ebook import writers
from sample_data import setup

class TestBaseHTMLWriter(unittest.TestCase):
    def setUp(self):
        setup(self)

        self.w = writers.BaseHTMLWriter()
        super(TestBaseHTMLWriter, self).setUp()

    def test_chapter_to_dom(self):
        self.fail("TODO: Implement")

    def test_story_to_dom(self):
        #TODO: Test more than the lack of exceptions.
        self.w.story_to_dom(self.chapterless_story)
        self.w.story_to_dom(self.empty_story)
