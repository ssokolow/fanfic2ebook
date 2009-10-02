# -*- coding: utf-8 -*-
"""Scrapers for fanfic2ebook

@todo:
 - Add a summary-extraction method and have the default implementation look for a paragraph
   beginning with "Summary: " or "Synopsis: ".
 - Add --cover and --comment (summary) support to TtHScraper.
 - Figure out why the FicWad scraper errors out when it passes the chapter
   associated with the URL fed to it.
 - Write a Scraper subclass for MediaMiner.
 - Make this code more robust (it makes many assumptions about cached data and input)
 - Support If-Modified-Since and ETag to further conserve bandwidth.
 - Add +http://www.ssokolow.com/scripts/ to the User-Agent string as soon as
   I'm ready to share this.
"""

__appname__ = "Fanfic Downloader for Pocket eBook Readers"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

# stdlib imports
import errno, os, re, urllib2, urlparse

# lxml imports
from lxml import html

# local imports
from data_structures import Story, Chapter

# -- Hopefully temporary hack to ensure safe stdout output --
import locale, sys
pref_enc = sys.stdout.encoding or locale.getpreferredencoding() or 'utf8'
def prnt(unistr):
    if isinstance(unistr, unicode):
        unistr = unistr.encode(pref_enc, 'ignore')
    print unistr
# --

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
            prnt("Not a %s story URL: %s" % (self.site_name, url))
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
                prnt("Chapter already exists. Skipping: %s" % target)
                continue

            if not pos + 1 in story.chapters:
                chap_tmp = self.acquire_chapter(chapter_url, story)[0]
                chap_tmp.path = target
                story.add_chapters(chap_tmp)

            prnt("Writing %s" % target)
            story.write(target, pos + 1)

        if self.bundle:
            story.path = os.path.join(fic_target,
                '%s.html' % self.prepare_filename(story.title))
            story.final_path = os.path.join(fic_target,
                '%s.%s' % (self.prepare_filename(story.title), self.final_ext.lstrip('.')))

            prnt("Generating single-file bundle: %s" % story.path)
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
                prnt("Target directory does not exist. Creating: %s" % target)
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
    story_title_re        = re.compile(r"^(?P<title>.+?)(,? Chapter (?P<chapter>.+?))?, an? (?P<category>.+?)( crossover)? fanfic" +
        " - FanFiction.Net$", re.IGNORECASE ) #: Used to extract the story's title and fandom from <title>

    def resolve_chapter_url(self, instr, base_url, dom):
        """Generate a Fanfiction.net chapter URL from the chapter number."""
        fic_id = urlparse.urlparse(base_url).path.split('/', 4)[2]
        return "http://www.fanfiction.net/s/%s/%s/" % (fic_id, instr)
    def get_story_title(self, dom):
        """Extract the story title from the Fanfiction.net <title> element."""
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
    chapter_content_xpath = ".//a[@name='storybody']/.."
    author_url_fragment   = '/AuthorStories-'

    def get_story_title(self, dom):
        """Extract the Twisting the Hellmouth story title"""
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
        """Extract the FicWad story title (Odder than it sounds)"""
        return dom.find('.//h3').getchildren()[-1].text
Scraper.register(FicWadScraper)
