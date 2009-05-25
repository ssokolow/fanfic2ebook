#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple fanfiction retrieval tool

Useful for generating personal archives or preparing fics to be converted to
ePub/BeBB/OEB/PDF/lit/MobiPocket/etc. for your portable eBook reader.

Features:
 - Autodetects story metadata. Requires only the URL for input.
 - Strips site templating to ensure a comfortable read on portable eBook readers.
 - Supports bundling all chapters into a single file for easy conversion.
 - Provides built-in support for converting to LRF, OEB, and ePub via Calibre.
 - Supports calling post-processors with keyword-substituted arguments.
 - Caches retrieved pages for convenience and efficiency. (and to avoid the risk
   of getting banned by fanfiction hosts for wasting bandwidth if it gets popular)

@todo:
 - Add a summary-extraction method and have the default implementation look for a paragraph
   beginning with "Summary: " or "Synopsis: ".
 - Add --cover and --comment (summary) support to TtHScraper.
 - I suspect it's not an encoding issue but a font issue that keeps certain
   accented characters from displaying in the Sony PRS-505. Offer an option to
   convert them to rough equivalents which can be displayed. (Common latin1
   accents like é and ï work but stuff like ō shows as whitespace) Make it default
   when the fanfic2lrf personality is active.
 - Figure out why the FicWad scraper errors out when it passes the chapter
   associated with the URL fed to it.
 - Write a Scraper subclass for MediaMiner.
 - Test the fanfic2oeb Personality and build upon it to write personalities based on
   oeb2mobi and oeb2lit.
 - Add support for passing profile flags to Calibre.
 - Make this code more robust (it makes many assumptions about cached data and input)
 - Finish re-architecting this so it meets my non-drowsy standards.
   (eg. passing arbitrary flags to html2lrf)
 - Support If-Modified-Since and ETag to further conserve bandwidth.
 - Add +http://www.ssokolow.com/scripts/ to the User-Agent string.
 - Look into replacing " and " with " & " in author strings to automatically
   support personalities which take &-separated lists of authors.

@newfield appname: Application Name
"""

__appname__ = "Fanfic Downloader for Pocket eBook Readers"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.0pre5"
__license__ = "GNU GPL 2.0 or later"

import errno, os, re, subprocess, sys, urllib2, urlparse
from lxml import html
from lxml.html import builder as E
from lxml.html.clean import Cleaner

# Set the User-Agent string
_opener = urllib2.build_opener()
_opener.addheaders = [('User-agent', '%s/%s' % (__appname__, __version__))]
urllib2.install_opener(_opener)

content_cleaner = Cleaner(scripts=True, javascript=True, comments=True,
        style=True, links=False, meta=True, page_structure=True,
        processing_instructions=True, embedded=True, frames=True,
        forms=True, annoying_tags=True, remove_unknown_tags=True,
        safe_attrs_only=True, remove_tags=['img']
        ) #: Used to sanitize chapter content.

class Story(object):
    """The in-memory representation of a story."""
    title    = None
    author   = None
    chapters = None
    category = ''
    cover    = ''

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
            toclist = E.UL()
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
    number  = None
    title   = None
    content = None

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

class Scraper(object):
    """The base class for fanfiction-to-ebook scrapers."""
    scrapers               = {} #: Scrapers registered to be called by L{get}
    site_name              = None #: Used by --list_supported.
    story_url_re           = None #: This regex determines which scrapers get which files.

    chapter_select_xpath   = None #: Used by L{acquire_chapter} to find the chapter list.
    chapter_content_xpath  = None #: Used by L{acquire_chapter} to find the chapter content.
    author_url_fragment    = None #: Used by L{acquire_chapter} to find the author's name.
    not_chapters           = ["story index", "table of contents"] #: Must be lowercase.

    chapter_title_re       = re.compile(r"^(?P<num>\d+)\. (?P<name>.*)$"
        ) #: Common to Fanfiction.net, FicWad, and TtH <select> elements.
    fat32_compatibility_re = re.compile('[\x00-\x19\x127"*/:<>?\\|]'
        ) #:Characters not allowed in FAT32 filenames.

    def __init__(self, target=None, bundle=False, final_ext='.out'):
        """
        Verifies the validity of the target path.

        @param target: The directory in which downloaded stories should be
            stored. Per-story directories will be created within this directory
            unless the sanitized title of the story matches the directory name.
            (it's more intuitive for end-users that way)
            Defaults to the current working directory if not specified.
        @param bundle: Whether to also generate a single-file copy of the story.
        @param final_ext: The extension to use when constructing the 'outfile'
            parameter to be passed to post-processors.
        @type target: str
        @type bundle: bool
        @type final_ext: str
        """
        self.bundle     = bundle
        self.final_ext  = final_ext
        self.target_dir = os.path.abspath(target or os.getcwd())
        self.verify_target_dir()

    def acquire_chapter(self, url, story=None):
        """Download and scrape a single chapter from a story.
        @param url: The URL of the chapter to download.
        @param story: The Story object provided by a previous run.
        @type url: str
        @type story: L{Story}

        @return: A tuple consisting of the newly-created L{Chapter} object and
            the L{Story} object which is either newly created or was provided
            as an argument.
        @rtype: (L{Chapter}, L{Story})
        """
        # Verify the URL's syntactical validity before wasting bandwidth.
        if not self.story_url_re.match(url):
            print "Not a %s story URL: %s" % (self.site_name, url)
            return None

        # Retrieve the raw chapter (don't keep the un-parsed HTML wasting memory)
        # .parse(handle) for proper encoding detection.
        # .urlopen for customizing the User-Agent header.
        dom = html.parse(urllib2.urlopen(url)).getroot()
        html.make_links_absolute(dom, copy=False)

        chapter_select  = dom.find(self.chapter_select_xpath)
        chapter_content = dom.find(self.chapter_content_xpath)

        if not story:
            author = ''
            for elem in dom.iterfind('.//a[@href]'):
                if self.author_url_fragment in elem.get('href'):
                    author = elem.text
                    break
            story = Story(self.get_story_title(dom), author)
            story.site_name = self.site_name
            story.category  = self.get_story_category(dom)
            if chapter_select is not None:
                options = chapter_select.findall(".//option")
                if options[0].text.strip().lower() in self.not_chapters:
                    options = options[1:]
                story.chapter_urls = [self.resolve_chapter_url(x.get('value'), url, dom) for x in options]
            else:
                story.chapter_urls = [url]

        cleaned = self.custom_content_cleaning(chapter_content)
        if cleaned is not None:
            chapter_content = cleaned

        # Extract metadata from the chapter selector (or recognize its absence)
        if chapter_select is not None:
            chapter_title_str = chapter_select.find(".//option[@selected]").text
            chapter_title_obj = self.chapter_title_re.match(chapter_title_str)

            chapter_title  = chapter_title_obj.group('name')
            chapter_number = int(chapter_title_obj.group('num'))

            chapter_num_str   = "Chapter %d" % chapter_number
            if not chapter_num_str.strip().lower() in chapter_title.strip().lower():
                chapter_title = chapter_num_str + ': ' + chapter_title
            chapter = Chapter(chapter_number, chapter_title, chapter_content)
        else:
            chapter = Chapter(1, '', chapter_content)

        return chapter, story

    def download_fic(self, url):
        """Download and save an entire story as a set of cleaned HTML files.

        @param url: The URL of any chapter in the story.
        @type url: str

        @return: A L{Story} object with a few extra properties.
        @rtype: L{Story}
        """
        # Prime the story-wide metadata store to get the chapter count
        story = self.acquire_chapter(url)[1]

        # Minimize the wasted bandwidth if it wasn't possible to avoid it
        # altogether. (and create the target dir if necessary)
        if os.path.basename(self.target_dir).strip().lower() == story.title.strip().lower():
            fic_target = self.target_dir
        else:
            fic_target = os.path.join(self.target_dir, self.prepare_filename(story.title))
            self.verify_target_dir(fic_target, create=True)

        for pos, chapter_url in enumerate(story.chapter_urls):
            target   = os.path.join(fic_target, "%s - %s.html" % (
                            self.prepare_filename(story.title), pos + 1))

            # Avoid re-downloading whenever possible
            if os.path.exists(target):
                chap_tmp = Chapter.from_html(target)
                chap_tmp.path = target
                story.add_chapters(chap_tmp)
                print "Chapter already exists. Skipping: %s" % target
                continue

            if not pos + 1 in story.chapters:
                chap_tmp = self.acquire_chapter(chapter_url, story)[0]
                chap_tmp.path = target
                story.add_chapters(chap_tmp)

            print "Writing %s" % target
            story.write(target, pos + 1)

        if self.bundle:
            story.path = os.path.join(fic_target,
                '%s.html' % self.prepare_filename(story.title))
            story.final_path = os.path.join(fic_target,
                '%s.%s' % (self.prepare_filename(story.title), self.final_ext.lstrip('.')))

            print "Generating single-file bundle: %s" % story.path
            story.write(story.path)

        return story

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
        target = target or self.target_dir

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
                print "Target directory does not exist. Creating: %s" % target
                os.makedirs(target)
            else:
                return False
        return True

    def get_story_title(self, dom):
        """Each L{Scraper} subclass overrides this to implement required functionality."""
        raise NotImplementedError("You must override this in a subclass")
    def resolve_chapter_url(self, instr, base_url, dom):
        """L{Scraper} subclasses override this if the values of the chapter <option>s are
            neither relative nor absolute URLs."""
        return urlparse.urljoin(base_url, instr)
    def get_story_category(self, dom):
        """L{Scraper} subclasses may override this to retrieve the category
           (eg. source series) that the fic falls into on the host site but
           it is not required."""
        return ''
    def custom_content_cleaning(self, content):
        """L{Scraper} subclasses may override this to implement site-specific
           clean-up of chapter content if necessary"""
        return content

    @classmethod
    def register(cls, scraper_class):
        """Register a new scraper to be retrieved by L{get} based on its
        L{story_url_re}.

        @param scraper_class: The scraper class to be registered.
        @type scraper_class: L{Scraper}
        """
        cls.scrapers[scraper_class.story_url_re] = scraper_class

    @classmethod
    def get(cls, url):
        """Retrieve a scraper capable of handling the given URL.
        See L{register} for more information.

        @param url: The URL to be used to identify the desired scraper.
        @type url: str

        @return: The L{Scraper} subclass capable of handling the given URL or
            None if no capable scraper is found.
        @rtype: C{class}|C{None}
        """

        for url_re in cls.scrapers:
            if url_re.match(url):
                return cls.scrapers[url_re]
        return None

class FFNetScraper(Scraper):
    """A fanfic-to-ebook scraper for Fanfiction.net"""
    site_name             = "Fanfiction.net"
    story_url_re          = re.compile(r"http://www.fanfiction.net/s/\d+/\d+/.*")

    chapter_select_xpath  = ".//*[@name='chapter']"
    chapter_content_xpath = ".//*[@class='storytext']"
    author_url_fragment   = '/u/'
    story_title_re        = re.compile(r"^(?P<title>.+?), an? (?P<category>.+?)( crossover)? fanfic" +
        " - FanFiction.Net$", re.IGNORECASE ) #: Used to extract the story's title and fandom from <title>

    def resolve_chapter_url(self, instr, base_url, dom):
        fic_id = urlparse.urlparse(base_url).path.split('/', 4)[2]
        return "http://www.fanfiction.net/s/%s/%s/" % (fic_id, instr)
    def get_story_title(self, dom):
        return self.story_title_re.match(dom.find('.//title').text).group('title')
    def get_story_category(self, dom):
        """Retrieve the category into which the story falls."""
        return self.story_title_re.match(dom.find('.//title').text).group('category')
Scraper.register(FFNetScraper)

class TtHScraper(Scraper):
    """A fanfic-to-ebook scraper for Twisting the Hellmouth"""
    site_name             = "Twisting the Hellmouth"
    story_url_re          = re.compile(r"http://www.tthfanfic.org/Story-\d+(-\d+)?(/.*)?")

    chapter_select_xpath  = ".//select[@id='chapnav']"
    chapter_content_xpath = ".//*[@class='storybody']"
    author_url_fragment   = '/AuthorStories-'

    def get_story_title(self, dom):
        return dom.find('.//h2').text
    def custom_content_cleaning(self, content):
        """Remove the site's chapter heading since we're adding our own."""
        elem_h3 = content.find('.//h3')
        elem_h3.getparent().remove(elem_h3)
Scraper.register(TtHScraper)

class FicWadScraper(Scraper):
    """A fanfic-to-ebook scraper for FicWad"""
    site_name             = "FicWad"
    story_url_re          = re.compile(r"http://www.ficwad.com/story/\d+")

    chapter_select_xpath  = ".//select[@name='goto']"
    chapter_content_xpath = ".//div[@id='storytext']"
    author_url_fragment   = '/author/'

    def get_story_title(self, dom):
        return dom.find('.//h3').getchildren()[-1].text
Scraper.register(FicWadScraper)

class Personality(object):
    """Defines an output mapping which can be accessed both by the -P argument
    and by alternatively-named symlinks."""
    personalities = {}              #: A class-level dict used by L{get}
    name          = 'fanfic2html'   #: The name by which the personality should be indexed.
    opts          = None            #: A dict of changes to make to the opts

    def postproc(self, story):
        """L{Personality} subclasses override this to define post-processor behaviour."""
        pass

    @classmethod
    def register(cls, personality_class):
        """Register a new personality to be retrieved by L{get} using its
        L{name}.

        @param personality_class: The personality class to be registered.
        @type personality_class: L{Personality}
        """

        if personality_class.name in cls.personalities:
            print "WARNING: Overriding existing personality name: %s" % personality_class.name
        cls.personalities[personality_class.name] = personality_class

    @classmethod
    def get(cls, name):
        """Retrieve a personality by name.
        See L{register} for more information.

        @param name: The name to be used to identify the desired personality.
        @type name: str

        @return: The L{Personalirt} subclass referenced by the given name or
            the base personality if no match is found.
        @rtype: C{class}
        """
        return cls.personalities.get(name, cls)
Personality.register(Personality)

class BBeBPersonality(Personality):
    """A personality for generating LRF files."""
    name  = 'fanfic2lrf'
    opts  = {'bundle' : True, 'final_ext' : '.lrf'}

    def postproc(self, story):
        """Perform the transformation from HTML to LRF."""
        cmdline = ['html2lrf', '-t', story.title, '-a', story.author,
            '-o', story.final_path, '--publisher', story.site_name]

        if story.category:
            cmdline.append('--category=%s' % story.category)
        if story.cover:
            cmdline.append('--cover=%s' % story.cover)
        cmdline.append(story.path)

        try:
            subprocess.check_call(cmdline)
            subprocess.check_call(['lrf-meta', '--classification=Fanfiction',
                '--creator=%s v%s' % (__appname__, __version__),
                story.final_path])
            return True
        except subprocess.CalledProcessError:
            return False
Personality.register(BBeBPersonality)

class EPubPersonality(Personality):
    """A personality for generating ePub files."""
    name  = 'fanfic2epub'
    opts  = {'bundle' : True, 'final_ext' : '.epub'}

    def postproc(self, story):
        """Perform the transformation from HTML to LRF."""
        cmdline = ['html2epub', '-t', story.title, '-a', story.author,
            '-o', story.final_path, '--publisher', story.site_name]

        if story.category:
            #TODO: Figure out how the PRS-505 displays ePub subjects.
            #FIXME: replace() commas with something else?
            cmdline.append('--subjects=%s' % story.category)
        if story.cover:
            cmdline.append('--cover=%s' % story.cover)
        cmdline.append(story.path)

        try:
            subprocess.check_call(cmdline)
            #TODO: Decide what to do with epub-meta.
            return True
        except subprocess.CalledProcessError:
            return False
Personality.register(EPubPersonality)

class OEBPersonality(Personality):
    """A personality for generating ePub files."""
    name  = 'fanfic2oeb'
    opts  = {'bundle' : True, 'final_ext' : '.oeb'}

    def postproc(self, story):
        """Perform the transformation from HTML to LRF."""
        cmdline = ['html2oeb', '-t', story.title, '-a', story.author,
            '-o', story.final_path, '--publisher', story.site_name]

        if story.category:
            #TODO: Figure out how the PRS-505 displays ePub subjects.
            #FIXME: replace() commas with something else?
            cmdline.append('--subjects=%s' % story.category)
        cmdline.append(story.path)

        try:
            subprocess.check_call(cmdline)
            #TODO: Decide what to do with epub-meta.
            return True
        except subprocess.CalledProcessError:
            return False
Personality.register(EPubPersonality)

if __name__ == '__main__':
    from optparse import OptionParser, OptionGroup

    descr  = ("A simple tool for archiving fanfiction for offline reading " +
    "and converting said archives into ready-to-read eBooks for pocket " +
    "reading devices.")

    epilog = ("As an alternative to explicitly specifying postproc strings, " +
    "this command will alter its behaviour if called by the following names:" +
    " " + ', '.join(sorted(Personality.personalities)))

    parser = OptionParser(version="%%prog v%s" % __version__,
        usage="%prog [options] <url> ...", description=descr, epilog=epilog)
    parser.add_option('-b', '--bundle', action="store_true", dest="bundle",
        default=False, help="Also bundle the entire story into a single file" +
                            "with chapter headings and a table of contents.")
    parser.add_option('-t', '--target', action="store", dest="target", metavar="DIR",
        default=os.getcwd(), help="Specify a target directory other than the current working directory.")
    parser.add_option('--list_supported', action="store_true", dest="list_supported",
        default=False, help="List sites supported by installed scrapers.")
    parser.add_option('-P', '--personality', action="store", dest="personality", metavar="NAME",
        default=None, help="Call the specified post-processor after each retrieval " +
                         "completes. Can be used multiple times. Implies --bundle.")

    pp_group = OptionGroup(parser, "Post-Processing Options")
    pp_group.add_option('-p', '--postproc', action="append", dest="postproc", metavar="CMD",
        default=[], help="Call the specified post-processor after each retrieval " +
                         "completes. Can be used multiple times. Implies --bundle.")
    pp_group.add_option('-e', '--final_ext', action="store", dest="final_ext", metavar="EXT",
        default=None, help="Set the extension to be used in the output filename " +
                           "available to post-processor templates.")
    parser.add_option_group(pp_group)

    opts, args = parser.parse_args()
    cmd = parser.get_prog_name()

    if opts.list_supported:
        names = sorted(Scraper.scrapers[x].site_name for x in Scraper.scrapers)
        print '\n'.join(names)
        sys.exit()

    if not args:
        parser.print_help()
        sys.exit()

    persona = Personality.get(opts.persona or cmd)
    for option in persona.opts:
        setattr(opts, option, persona.opts[option])

    if opts.postproc:
        opts.bundle = True

    for url_arg in args:
        scraper = Scraper.get(url_arg)(opts.target, opts.bundle, opts.final_ext)
        downloaded_story = scraper.download_fic(url_arg)

        persona.postproc(downloaded_story)

        if opts.postproc:
            inputs = {
                'appname'   : "%s v%s" % (__appname__, __version__),
                'author'    : downloaded_story.author,
                'bundle'    : downloaded_story.path,
                'category'  : downloaded_story.category,
                'coverfile' : downloaded_story.cover,
                'outfile'   : downloaded_story.final_path,
                'site_name' : downloaded_story.site_name,
                'title'     : downloaded_story.title
            }

            for pp_cmdline in opts.postproc:
                cmdlist = pp_cmdline.strip().split()
                print "Calling post-processor: %s" % cmdlist[0]
                subprocess.call([r % inputs for r in cmdlist])
