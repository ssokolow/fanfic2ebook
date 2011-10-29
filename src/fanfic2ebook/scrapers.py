# -*- coding: utf-8 -*-
"""Site scraper definitions

@todo:
 - Add a summary-extraction method and have the default implementation look for a paragraph
   beginning with "Summary: " or "Synopsis: ".
 - Add --cover and --comment (summary) support to TtHScraper.
 - Figure out why the FicWad scraper errors out when it passes the chapter
   associated with the URL fed to it.
 - Write a Scraper subclass for MediaMiner.
 - Make this code more robust (it makes many assumptions about cached data and input)
 - Consider adding ETags and If-Modified-Since support to the urllib2 fallback.
 - Check out the sites listed at http://www.ficsavers.com/index.cgi?action=list
"""

import logging
log = logging.getLogger(__name__)

# stdlib imports
import re, urlparse

# lxml imports
from lxml import html
from lxml.etree import XPath
from lxml.cssselect import CSSSelector

# local imports
from data_structures import Registerable, Story, Chapter
from retrieval import HTTP

def regex_key_matcher(cls, url, fallback=None):
    """Matcher for L{Registerable} which uses tests regexes instead."""
    for url_re in cls.subclasses:
        if url_re.match(url):
            return cls.subclasses[url_re]
    return fallback

class BaseScraper(Registerable):
    story_url_re           = None #: This regex determines which scrapers get which files.
    name                   = None #: Used by --list_supported.
BaseScraper.init_registry(key_getter=lambda x: x.story_url_re,
        key_matcher=regex_key_matcher)

#TODO: Switch to using Registerable's implementation.
class Scraper(BaseScraper):
    #TODO: chapter_select_xpath should be delegated to a mixin.
    chapter_select_xpath   = None #: Used by L{acquire_chapter} to find the chapter list.
    chapter_content_xpath  = None #: Used by L{acquire_chapter} to find the chapter content.
    author_url_fragment    = None #: Used by L{acquire_chapter} to find the author's name.
    not_chapters           = ["story index", "table of contents"] #: Must be lowercase.

    #TODO: Make this take either a CSSSelector object or an XPath object.
    unwanted_elements      = []   #: Set to a list of CSS selectors to remove things.

    chapter_title_re       = re.compile(r"^(?P<num>\d+)\. (?P<name>.*)$"
        ) #: Common to Fanfiction.net, FicWad, and TtH <select> elements.
    def __init__(self, retriever=HTTP):
        self.http = retriever()
        self.removal_selectors = [CSSSelector(x) for x in self.unwanted_elements]

    def acquire_chapter(self, url, story=None):
        """Download and scrape a single chapter from a story.
        @param url: The URL of the chapter to download.
        @param story: The Story object provided by a previous run.
        @type url: str
        @type story: L{Story}

        @return: A tuple consisting of the newly-created L{Chapter} object and
            the L{Story} object which is either newly created or was provided
            as an argument.
        @rtype: L{Chapter}
        """
        # Verify the URL's syntactical validity before wasting bandwidth.
        if not self.story_url_re.match(url):
            log.error("Not a %s story URL: %s", self.name, url)
            return None

        # Retrieve the raw chapter (don't keep the un-parsed HTML wasting memory)
        # .parse(handle) for proper encoding detection.
        # .urlopen for customizing the User-Agent header.
        dom = self.http.get_dom(url)
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
            story.publisher = self.name
            story.categories  = self.get_story_categories(dom)
            if chapter_select is not None:
                options = chapter_select.findall(".//option")
                if options[0].text.strip().lower() in self.not_chapters:
                    options = options[1:]
                story.chapter_urls = [self.resolve_chapter_url(x.get('value'), url, dom) for x in options]
            else:
                story.chapter_urls = [url]

        for selector in self.removal_selectors:
            [x.getparent().remove(x) for x in selector(chapter_content)]

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

        chapter.story = story
        return chapter

    #TODO: Instead of writing to disk, yield Chapter objects one-by-one
    # since, being already I/O-bound, we might as well be memory-efficient too.
    def download_fic(self, url):
        """Download and save an entire story as a set of cleaned HTML files.

        @param url: The URL of any chapter in the story.
        @type url: str

        @return: A L{Story} object with a few extra properties.
        @rtype: L{Story}
        """
        # Prime the story-wide metadata store to get the chapter count
        story = self.acquire_chapter(url).story

        for pos, chapter_url in enumerate(story.chapter_urls):
            if not pos + 1 in story.chapters:
                #TODO: Do this without abusing @property.
                story.chapters = self.acquire_chapter(chapter_url, story)

        return story

    def get_story_title(self, dom):
        """Override to extract the story title."""
        raise NotImplementedError("You must override this in a subclass")

    def resolve_chapter_url(self, instr, base_url, dom):
        """Override this if the values of the chapter <option>s are neither
           relative nor absolute URLs."""
        return urlparse.urljoin(base_url, instr)
    def get_story_categories(self, dom):
        """(optional) Override to implement scraping of categories/fandoms/etc."""
        return ''
    def custom_content_cleaning(self, content):
        """Override to implement site-specific clean-up of chapter content"""
        return content

class FFNetScraper(Scraper):
    """A fanfic-to-ebook scraper for Fanfiction.net"""
    name             = "Fanfiction.net"
    story_url_re     = re.compile(r"http://www.fanfiction.net/s/\d+/\d+/.*")

    chapter_select_xpath  = ".//*[@name='chapter']"
    chapter_content_xpath = ".//*[@class='storytext']"
    author_url_fragment   = '/u/'
    unwanted_elements     = ['.a2a_kit']
    story_title_re        = re.compile(r"^(?P<title>.+?)(,? Chapter (?P<chapter>.+?))?, an? (?P<category>.+?)( crossover)? fanfic" +
        " - FanFiction.Net$", re.IGNORECASE ) #: Used to extract the story's title and fandom from <title>

    def resolve_chapter_url(self, instr, base_url, dom):
        """Generate a Fanfiction.net chapter URL from the chapter number."""
        fic_id = urlparse.urlparse(base_url).path.split('/', 4)[2]
        return "http://www.fanfiction.net/s/%s/%s/" % (fic_id, instr)
    def get_story_title(self, dom):
        """Extract the story title from the Fanfiction.net <title> element."""
        return self.story_title_re.match(dom.find('.//title').text).group('title')
    def get_story_categories(self, dom):
        """Retrieve the category into which the story falls."""
        #TODO: Handle crossovers properly
        return [self.story_title_re.match(dom.find('.//title').text).group('category')]
FFNetScraper.register()

class TtHScraper(Scraper):
    """A fanfic-to-ebook scraper for Twisting the Hellmouth"""
    name             = "Twisting the Hellmouth"
    story_url_re     = re.compile(r"http://www.tthfanfic.org/(Story-\d+(-\d+)?(/.*)?|story.php\?no=\d+)")

    chapter_select_xpath  = ".//select[@id='chapnav']"
    chapter_content_xpath = ".//a[@name='storybody']/.."
    author_url_fragment   = '/AuthorStories-'
    unwanted_elements     = ['h3']

    def get_story_title(self, dom):
        return dom.find('.//h2').text
TtHScraper.register()

class FicWadScraper(Scraper):
    """A fanfic-to-ebook scraper for FicWad"""
    name             = "FicWad"
    story_url_re     = re.compile(r"http://www.ficwad.com/story/\d+")

    chapter_select_xpath  = ".//select[@name='goto']"
    chapter_content_xpath = ".//div[@id='storytext']"
    author_url_fragment   = '/author/'

    def get_story_title(self, dom):
        """Extract the FicWad story title (Odder than it sounds)"""
        return dom.find('.//h3').getchildren()[-1].text
FicWadScraper.register()
