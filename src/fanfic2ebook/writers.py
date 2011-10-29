# -*- coding: utf-8 -*-
"""Serializers for fanfic2ebook"""

import logging
log = logging.getLogger(__name__)

import errno, os
from lxml import html
from lxml.html import builder as E

from data_structures import Registerable

class BaseWriter(Registerable):
    """Base class for all Writers."""

    def write(self, story, path):
        """Serialize the given C{story} to C{path}."""
        raise NotImplementedError("Writing not implemented in this writer.")
BaseWriter.init_registry()

class BaseHTMLWriter(BaseWriter):
    """Code common to C{HTML*Writer} classes."""

    def chapter_to_dom(self, chapter):
        """Generate a clean HTML DOM from the stored information.

        @return: An lxml DOM.
        @rtype: C{lxml.html.HtmlElement}
        """
        elem_name = 'chapter_%d' % chapter.number
        return E.DIV(E.CLASS('chapter'),
            E.H2( E.CLASS('chapter_title'), chapter.title),
            E.A(  E.CLASS('chapter_num'),   id=elem_name, name=elem_name),
            E.DIV(E.CLASS('content'),       chapter.content)
        )

    #TODO: Rework this to take a slice or equivalent for easy chunking.
    def story_to_dom(self, story, only_chapter=None):
        """Generate a clean HTML DOM from the stored information.

        @param only_chapter: Generate a single-chapter DOM from the chapter
            number given. (1-based numbering)
        @type only_chapter: int

        @return: An lxml DOM.
        @rtype: C{lxml.html.HtmlElement}
        """
        #Build the body's header
        body = E.BODY(
                E.H1(story.title, id='title'),
                E.DIV("By: ", E.SPAN(story.author, id='author')))

        # Generate the table of contents
        if len(story.chapters) > 1 and not only_chapter:
            toclist = E.OL()
            for num in sorted(story.chapters):
                chapter = story.chapters[num]
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
            body.append(self.chapter_to_dom(story.chapters[only_chapter]))
        else:
            for num in sorted(story.chapters):
                chapter = story.chapters[num]
                body.append(self.chapter_to_dom(chapter))

        # Add the header and top-level element
        document = E.HTML(E.HEAD(E.TITLE(story.title)), body)
        return document

    def prepare_filename(self, in_str):
        """Given a story title or other unsafe string, sanitize any characters
        which cannot be put into FAT32 long filenames.

        @param in_str: Any string to be be used as a filename component.
        @type in_str: str|unicode

        @return: The sanitized string.
        @rtype: str|unicode"""
        return self.fat32_compatibility_re.sub('_', in_str)

    def verify_target_dir(self, target=None, create=False):
        """Check the given path to ensure it's suitable for saving stories.

        @param target: The directory to be checked for apropriateness.
        @param create: Indicates whether to create the target directory if it
            does not exist.
        @type target: str
        @type create: bool

        @return: True if the directory exists or has been created. False otherwise.
        @rtype: bool

        @raise IOError: Raises IOError when the target is not a directory or
            we lack insufficient permissions.

        @todo: Make sure this handles Unicode properly.
        """
        if os.path.exists(target):
            if not os.path.isdir(target):
                raise IOError(errno.ENOTDIR, errno.errorcode[errno.ENOTDIR], target)
            if not os.access(target, os.W_OK):
                raise IOError(errno.EACCES, "%s (%s)" % (errno.errorcode[errno.EACCES],
                    "Target directory is not writable."), target)
        else:
            parent = os.path.split(target)[0]
            if not os.access(parent, os.W_OK | os.X_OK):
                raise IOError(errno.EACCES, "%s (%s)" % (errno.errorcode[errno.EACCES],
                    "Target directory does not exist and cannot be created."), parent)
            elif create:
                log.info("Target directory does not exist. Creating: %s", target)
                os.makedirs(target)
            else:
                return False
        return True

class HTMLDirWriter(BaseHTMLWriter):
    """Write a story as a set of HTML files in a folder."""
    name = 'htmldir'

    def __init__(self, overwrite=False):
        super(HTMLDirWriter, self).__init__()
        self.overwrite = overwrite

    def write(self, story, path):
        for num in story.chapters:
            #TODO: Ponder zero-padding the name here.
            target = os.path.join(path, "%s - %s.html" % (
                         self.prepare_filename(story.title),
                         num))

            # Avoid wasting time re-writing existing chapters.
            if os.path.exists(target) and not self.overwrite:
                log.info("Chapter already exists. Skipping: %s", target)
                continue

            with open(path, 'w') as outfile:
                log.info("Writing chapter %s to HTML: %s", num, path)
                outfile.write(html.tostring(self.story_to_dom(story, num),
                    include_meta_content_type=True))
HTMLDirWriter.register()

class HTMLFileWriter(BaseHTMLWriter):
    """Write an entire story as a single file."""
    name = 'htmlfile'

    def write(self, story, path):
        """Serialize the given C{story} to C{path}."""
        file_path = os.path.join(path,
            '%s.html' % self.prepare_filename(story.title))

        with open(file_path, 'w') as outfile:
            log.info("Generating single-file bundle: %s", path)
            outfile.write(html.tostring(self.story_to_dom(story),
                    include_meta_content_type=True))

class Story(object):
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
    #XXX: Duplicate story metainfo here to make chapter data more reliably complete?
    meta_mappings = {
            'DC.identifier' : 'chapter_url',
    } #: @todo: Implement

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

