# -*- coding: utf-8 -*-
"""Data structures for fanfic2ebook"""

__appname__ = "Fanfic Downloader for Pocket eBook Readers"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import os
from lxml import html
from lxml.html import builder as E
from lxml.html.clean import Cleaner

content_cleaner = Cleaner(scripts=True, javascript=True, comments=True,
        style=True, links=False, meta=True, page_structure=True,
        processing_instructions=True, embedded=True, frames=True,
        forms=True, annoying_tags=True, remove_unknown_tags=True,
        safe_attrs_only=True, remove_tags=['img']
        ) #: Used to sanitize chapter content.

class Story(object):
    """The in-memory representation of a story."""
    title      = None
    author     = None #XXX: Should I just trust sites to specify a primary author or plan for co-authorship?
    author_url = None #: @todo: Implement
    chapters   = None
    category   = ''
    cover      = ''
    language   = None #: @todo: Implement (http://www.ietf.org/rfc/rfc3066.txt and http://xml.coverpages.org/iso639a.html)
    published  = None #: @todo: Implement
    publisher  = None #: @todo: Implement (Name of the fic-hosting site from which it was retrieved)
    story_url  = None #: @todo: Implement
    summary    = ''   #: @todo: Implement
    updated    = None #: @todo: Implement (What about at the chapter level? Story updated value as of initial retrieval in an incremental save?)

    meta_mappings = {
            'Author' : 'author',
            'DC.title' : 'title', #TODO: What about chapter title vs. story title? ...and what about speccing <title> more formally?
            'DC.creator' : 'author',
            'DC.date.created' : 'published',
            'DC.date.modified' : 'updated',
            'DC.description' : 'summary',
            'DC.language' : 'language',
            'DC.publisher' : 'publisher',
            'Description' : 'summary',
            'Language' : 'language', #TODO:
            'Identifier-URL' : 'story_url',
            #TODO: Rating, Charset
    } #: @todo: Implement

    meta_fixed = {
            'Category' : 'Fanfiction',
            'DC.type' : 'Text',
            'Generator' : 'fanfic2ebook', #TODO: Use the User Agent string here
            #TODO: Include a schema versioning meta element.
    } #: @todo: Implement

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
        self.chapters = {}

        if chapters:
            self.add_chapters(chapters)

    def __repr__(self):
        return "<Chapter(%s, %s, %s)>" % (repr(self.title),
            repr(self.author), self.chapters and '...' or None)

    def add_chapters(self, chapters):
        """Add chapters to the story

        @param chapters: Chapter(s) to add.
        @type chapters: L{Chapter} or C{dict}/iterable of L{Chapter}s.
        """
        # Support directly passing single chapters
        if isinstance(chapters, Chapter):
            chapters = [chapters]

        # Support both in-order and un-ordered addition
        if not isinstance(chapters, dict):
            chapters = dict((pos, val) for pos, val in enumerate(chapters))

        for chapter_num in chapters:
            chapter_obj = chapters[chapter_num]
            chapter_pos = int(chapter_obj.number)
            if chapter_pos in self.chapters:
                print "WARNING: Overwriting existing chapter %d" % chapter_pos
            self.chapters[chapter_pos] = chapter_obj

    def to_dom(self, only_chapter=None):
        """Generate a clean HTML DOM from the stored information.

        @param only_chapter: Generate a single-chapter DOM from the chapter
            number given. (1-based numbering)
        @type only_chapter: int

        @return: An lxml DOM.
        @rtype: C{lxml.html.HtmlElement}
        """
        #Build the body's header
        body = E.BODY(
                E.H1(self.title, id='title'),
                E.DIV("By: ", E.SPAN(self.author, id='author')))

        # Generate the table of contents
        if len(self.chapters) > 1 and not only_chapter:
            toclist = E.OL()
            for chapter_num in sorted(self.chapters):
                chapter = self.chapters[chapter_num]
                toclist.append(E.LI(
                    E.A(chapter.title, href="#chapter_%d" % chapter.number)
                ))
            body.append(E.DIV(
                E.H2("Table of Contents"),
                toclist,
                id='toc'
            ))

        # Build the chapter(s)
        if only_chapter:
            body.append(self.chapters[only_chapter].to_dom())
        else:
            for chapter_num in sorted(self.chapters):
                chapter = self.chapters[chapter_num]
                body.append(chapter.to_dom())

        # Add the header and top-level element
        document = E.HTML(E.HEAD(E.TITLE(self.title)), body)
        return document

    def write(self, path, only_chapter=None):
        """Serialize to file using L{to_dom}.

        @param path: The path to write the content to.
        @param only_chapter: See L{to_dom}.
        @type path: str
        @type only_chapter: int
        """
        outfile = open(path, 'w')
        outfile.write(html.tostring(self.to_dom(only_chapter)))
        outfile.close()

    @staticmethod
    def from_html(path):
        """Load a story and any available chapters from a DOM, path, string, or
        file-like object.

        @param path: A DOM, path, string, or file-like object
            originating with L{to_dom}.
        @type path: C{basestring} or file-like object

        @return: A Story object.
        @rtype: L{Story}"""
        doc = html.parse(path).getroot()
        story = Story(
            doc.get_element_by_id('title').text,
            doc.get_element_by_id('author').text)

        for chapter in doc.find_class('chapter'):
            story.add_chapters(Chapter.from_html(chapter))

        return story

class Chapter(object):
    """The in-memory representation of a chapter"""
    number      = None
    title       = None
    content     = None
    chapter_url = None #TODO: Implement

    #XXX: Duplicate story metainfo here to make chapter data more reliably complete?
    meta_mappings = {
            'DC.identifier' : 'chapter_url',
    } #: @todo: Implement

    def __init__(self, number, title, content):
        """
        @param  number: The chapter's position in the story.
        @param   title: The chapter's title.
        @param content: The actual chapter content.
        @type  number: int
        @type   title: basestring
        @type content: lxml.html.HtmlElement
        """
        content_cleaner(content)

        self.number  = number
        self.title   = title
        self.content = content

    def __repr__(self):
        return "<Chapter(%s, %s, %s)>" % (repr(self.number),
            repr(self.title), self.content and '...' or None)

    def to_dom(self):
        """Generate a clean HTML DOM from the stored information.

        @return: An lxml DOM.
        @rtype: C{lxml.html.HtmlElement}
        """
        elem_name = 'chapter_%d' % self.number
        return E.DIV(E.CLASS('chapter'),
            E.H2( E.CLASS('chapter_title'), self.title),
            E.A(  E.CLASS('chapter_num'),   id=elem_name, name=elem_name),
            E.DIV(E.CLASS('content'),       self.content)
        )

    @staticmethod
    def from_html(html_in):
        """Load a chapter from a DOM, path, string, or file-like object

        @param html_in: An lxml HTML DOM, path, string, or file-like object
            containing a chapter written out by L{to_dom}.
        @type html_in: C{lxml.html.HtmlElement},C{basestring}, or file-like object

        @return: A Chapter object.
        @rtype: L{Chapter}"""
        if isinstance(html_in, html.HtmlElement):
            doc = html_in
        elif isinstance(html_in, basestring) and not os.path.exists(html_in):
            doc = html.fromstring(html_in)
        else:
            doc = html.parse(html_in).getroot()

        chapter_title = doc.find_class('chapter_title')[0].text or ''
        return Chapter(
            int(doc.find_class('chapter_num')[0].get('name').lstrip('chapter_')),
            chapter_title,
            doc.find_class('content')[0].getchildren()[0])
