"""
@todo: Decide whether empty_* should error out on __init__.
"""

import unittest

from sample_data import setup

class TestStory(unittest.TestCase):
    def setUp(self):
        setup(self)

    def test_defaults(self):
        self.assertEqual(self.empty_story.language, 'en',
                "Default language 'en' did not get set on empty story")

class TestChapter(unittest.TestCase):
    def setUp(self):
        setup(self)

    def test_foo(self):
        self.fail("TODO: Need to implement tests here")
