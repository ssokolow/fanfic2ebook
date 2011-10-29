# -*- coding: utf-8 -*-
"""Data structures for fanfic2ebook"""

import logging
log = logging.getLogger(__name__)

from lxml.html.clean import Cleaner

content_cleaner = Cleaner(
        scripts=True,
        javascript=True,
        comments=True,
        style=True,
        links=False,
        meta=True,
        page_structure=True,
        processing_instructions=True,
        embedded=True,
        frames=True,
        forms=True,
        annoying_tags=True,
        remove_unknown_tags=True,
        safe_attrs_only=True,
        remove_tags=['img'] #TODO: Decide whether to eventually support images.
        ) #: Used to sanitize chapter content.

class Story(object):
    """The in-memory representation of a story."""
    #TODO: Verify all these got populated by the scrapers.
    title      = None
    author     = None #XXX: Should I just trust sites to specify a primary author or plan for co-authorship?
    author_url = None #: @todo: Implement
    _chapters  = None
    categories = None
    cover      = ''
    language   = 'en' #: @todo: Implement (http://www.ietf.org/rfc/rfc3066.txt and http://xml.coverpages.org/iso639a.html)
    published  = None #: @todo: Implement
    publisher  = None #: @todo: Implement (Name of the fic-hosting site from which it was retrieved)
    rating     = None #: @todo: Implement
    series     = None #: @todo: Implement
    series_pos = None #: @todo: Implement
    story_url  = None #: @todo: Implement
    summary    = ''   #: @todo: Implement
    updated    = None #: @todo: Implement (What about at the chapter level? Story updated value as of initial retrieval in an incremental save?)

    #TODO: Think more on what should really be required or optional.
    def __init__(self, title, author, chapters=None):
        """
        @param    title: The story's title
        @param   author: The author's name
        @param chapters: See L{add_chapters}
        @type    title: basestring
        @type   author: basestring
        """
        self.title    = title
        self.author   = author
        self.chapters = chapters or {}
        self.categories = []

    def __repr__(self):
        return "<Chapter(%s, %s, %s)>" % (repr(self.title),
            repr(self.author), self.chapters and '...' or None)

    @property
    def chapters(self):
        return self._chapters

    @chapters.set
    def chapters(self, value):
        """Default to append rather than replace for chapter list.

        @todo: Re-think this and stop relying on it in L{Scraper}.
        """
        if not value:
            self._chapters = {}
            return

        # Support directly passing single chapters
        chapters = [value] if isinstance(value, Chapter) else value

        # Support both in-order and un-ordered addition
        if not isinstance(chapters, dict):
            chapters = dict((pos, val) for pos, val in enumerate(chapters))

        for num in chapters:
            obj = chapters[num]
            obj.story = self
            pos = int(obj.number)

            if pos in self._chapters:
                log.warn("Overwriting existing chapter %d" % pos)

            self._chapters[pos] = obj

class Chapter(object):
    """The in-memory representation of a chapter"""
    #TODO: Verify all these got populated by the scrapers.
    number      = None #TODO: Should I use @property to constrain the values of number?
    story       = None
    title       = None
    _content    = None
    chapter_url = None #TODO: Amend the writers to serialize this too.

    def __init__(self, number, title, content):
        """
        @param  number: The chapter's position in the story.
        @param   title: The chapter's title.
        @param content: The actual chapter content.
        @type  number: int
        @type   title: basestring
        @type content: lxml.html.HtmlElement

        @todo: Should I accept and auto-parse strings for content?
        """
        self.number  = number
        self.title   = title
        self.content = content

    def __repr__(self):
        return "<Chapter(%s, %s, %s)>" % (repr(self.number),
            repr(self.title), self.content and '...' or None)

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value
        if value is not None:
            content_cleaner(self._content)

class Registerable(object):
    """Defines a class which can register and look up subclasses by name."""
    subclasses = {}     #: A class-level dict used by L{get}
    name = None         #: Override in subclasses to define the lookup key

    @classmethod
    def init_registry(cls):
        """Declare this as the root of a new lookup registry."""
        cls.subclasses = {}

    @classmethod
    def register(cls, set_fallback=False):
        """Register a new subclass to be retrieved by L{get} using its L{name}."""

        if cls.name in cls.subclasses:
            log.warn("Replacing existing subclass: %s", cls.name)
        cls.subclasses[cls.name] = cls

    @classmethod
    def get(cls, name, fallback=None):
        """Retrieve a subclass by name.
        See L{register} for more information.

        @param name: The value of the desired class's name member.
        @type name: str

        @return: The subclass referenced by the given name or C{fallback}.
        @rtype: C{class}
        """
        return cls.subclasses.get(name, fallback)
