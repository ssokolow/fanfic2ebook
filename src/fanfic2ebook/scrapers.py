# -*- coding: utf-8 -*-
"""Site scraper definitions

@todo:
 - Add a summary-extraction method and have the default implementation look for
   a paragraph beginning with "Summary: " or "Synopsis: ".
 - Add --cover and --comment (summary) support to TtHScraper.
 - Figure out why the FicWad scraper errors out when it passes the chapter
   associated with the URL fed to it.
 - Write a Scraper subclass for MediaMiner.
 - Make it more robust (it makes many assumptions about cached data and input)
 - Consider adding ETags and If-Modified-Since support to the urllib2 fallback.
 - Check out the sites listed at http://www.ficsavers.com/index.cgi?action=list
 - See if this is immediately relevant:
   http://lxml.de/xpathxslt.html#regular-expressions-in-xpath
 - Consider supporting some kind of learning behaviour to produce a draft
   version of the new XPath expression when FFnet changes their layout.
   (Based on identifying what it SHOULD return from metadata cached from
   previous chapters and then figuring out how to retrieve that from the DOM.)
"""

import logging
log = logging.getLogger(__name__)

# stdlib imports
import re, urlparse

# lxml imports
from lxml import html
from lxml.etree import XPath
from lxml.cssselect import CSSSelector as CSS

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
    story_url_re           = None  #: This regex picks which scraper for a file
    name                   = None  #: Used by --list_supported.
BaseScraper.init_registry(key_getter=lambda x: x.story_url_re,
        key_matcher=regex_key_matcher)

#TODO: Write some unit tests for this which catch grabbing pages twice.
class Scraper(BaseScraper):
    #TODO: Work to make these names as consistent as possible
    author_name_selector     = None  #: Gets author name for L{acquire_chapter}
    story_title_selector     = None  #: Used by L{acquire_chapter}
    chapter_nodes_selector    = None  #: Chapter list for L{acquire_chapter}
    chapter_title_selector   = None
    chapter_content_selector = None  #: Chapter content for L{acquire_chapter}
    not_chapters             = ["story index", "table of contents"]  #: Must be lowercase.
    unwanted_elements        = []   #: CSS or XPath selectors to remove things.

    chapter_title_re       = re.compile(
            r"^(?P<num>\d+)\. (?P<name>.*)$"
    )  #: Common to Fanfiction.net, FicWad, and TtH <select> elements.

    def __init__(self, retriever=HTTP):
        self.http = retriever()

    def _first_str(self, dom, selectors):
        """Take a selector or selector chain and return a stripped unicode()"""
        if not isinstance(selectors, (list, tuple)):
            selectors = [selectors]

        for stage in selectors:
            #TODO: Make this regex-compatible
            results = stage(dom)
            if isinstance(results, list):
                dom = results[0]
            elif results:
                dom = results
            else:
                log.debug("Match failed: %s(%s) in %s", stage, dom, self.name)
                return None

        #TODO: Decide on a consistent plan for how to handle chained selectors
        #      (return types, conversion to str(), etc.)
        return unicode(dom.strip())

    def acquire_chapter(self, url, story=None, base_url=None):
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
        # TODO: I may want to just trust the lookup to do this.
        #       (I'm getting a gut feeling that base_url will prove a kludge)
        if not self.story_url_re.match(base_url or url):
            log.error("Not a %s story URL: %s", self.name, url)
            return None

        # Retrieve the raw chapter (don't keep un-parsed HTML wasting memory)
        # .parse(handle) for proper encoding detection.
        # .urlopen for customizing the User-Agent header.
        dom = self.http.get_dom(url)
        html.make_links_absolute(dom, copy=False)

        #TODO: Need some error handling here
        chapter_content = self.chapter_content_selector(dom)[0]
        chapter_nodes  = self.chapter_nodes_selector(dom)

        if not story:
            #TODO: Need to decide where, in a loosely-coupled stack, selector
            #      failure should be checked (given that different apps may
            #      have different standards) and how to react to it.
            story = Story(
                    title=self._first_str(dom, self.story_title_selector),
                    author=self._first_str(dom, self.author_name_selector))
            story.publisher = self.name
            story.categories  = self.get_story_categories(dom)
            if len(chapter_nodes):
                options = [x for x in chapter_nodes if x.text.strip().lower() not in self.not_chapters]
                story.chapter_urls = [self.resolve_chapter_url(x.get('value'), url, dom) for x in options]
            else:
                story.chapter_urls = [url]

        for selector in self.unwanted_elements:
            [x.getparent().remove(x) for x in selector(chapter_content)]

        #FIXME: Once content processing is done, IDs need to be stripped.
        cleaned = self.custom_content_cleaning(chapter_content)
        if cleaned is not None:
            chapter_content = cleaned

        # Extract metadata from the chapter selector (or recognize its absence)
        chapter_title_str = self.chapter_title_selector(dom)
        if chapter_title_str:
            chapter_title_obj = self.chapter_title_re.match(chapter_title_str[0])

            chapter_title  = chapter_title_obj.group('name')
            chapter_number = int(chapter_title_obj.group('num'))

            chapter = Chapter(chapter_number, chapter_title, chapter_content)
        else:
            chapter = Chapter(1, '', chapter_content)

        chapter.story = story
        return chapter

    #TODO: Instead of writing to disk, yield Chapter objects one-by-one
    # since, being already I/O-bound, we might as well be memory-efficient too.
    def download_fic(self, url, base_url=None):
        """Download and save an entire story as a set of cleaned HTML files.

        @param url: The URL of any chapter in the story.
        @type url: str

        @return: A L{Story} object with a few extra properties.
        @rtype: L{Story}
        """
        # Prime the story-wide metadata store to get the chapter count
        story = self.acquire_chapter(url, base_url=base_url).story

        for pos, chapter_url in enumerate(story.chapter_urls):
            if not pos + 1 in story.chapters:
                #TODO: Do this without abusing @property.
                story.chapters = self.acquire_chapter(chapter_url, story)

        return story

    def resolve_chapter_url(self, instr, base_url, dom):
        """Override this if the values of the chapter <option>s are neither
           relative nor absolute URLs."""
        return urlparse.urljoin(base_url, instr)

    def get_story_categories(self, dom):
        """(optional) Override to scrape categories/fandoms/etc."""
        return ''

    def custom_content_cleaning(self, content):
        """Override to implement site-specific clean-up of chapter content"""
        return content

class FFNetScraper(Scraper):
    """A fanfic-to-ebook scraper for Fanfiction.net"""
    name             = "Fanfiction.net"
    story_url_re     = re.compile(r"http://www.fanfiction.net/s/\d+/\d+/.*")

    author_name_selector     = XPath(".//a[contains(@href, '/u/')]/text()")
    chapter_content_selector = CSS('.storytext')
    chapter_nodes_selector   = XPath(".//*[@name='chapter']//option")
    chapter_title_selector   = XPath(".//*[@name='chapter']//option[@selected]/text()")
    story_title_selector     = XPath(".//div[@id='profile_top']/b/text()")
    unwanted_elements        = [CSS('.a2a_kit')]
    #TODO: Handle crossovers properly
    get_story_categories     = XPath(".//*[@id='pre_story_links']//a[@class='xcontrast_txt'][last()]/text()")

    def resolve_chapter_url(self, instr, base_url, dom):
        """Generate a Fanfiction.net chapter URL from the chapter number."""
        fic_id = urlparse.urlparse(base_url).path.split('/', 4)[2]
        return "http://www.fanfiction.net/s/%s/%s/" % (fic_id, instr)
FFNetScraper.register()

class WGotFFNetScraper(FFNetScraper):
    """@todo: Figure out a way to more properly match downloaded files."""
    name             = "Fanfiction.net (wget-retrieved files)"
    story_url_re     = re.compile(r".*\.\d+\.html")

    def resolve_chapter_url(self, instr, base_url, dom):
        """Generate a Fanfiction.net chapter URL from the chapter number."""
        split_path = base_url.rsplit('.', 2)
        split_path[1] = ('%0' + str(len(split_path[1])) + 'd') % int(instr)
        return '.'.join(split_path)
WGotFFNetScraper.register()

class TtHScraper(Scraper):
    """A fanfic-to-ebook scraper for Twisting the Hellmouth"""
    name             = "Twisting the Hellmouth"
    story_url_re     = re.compile(r"http://www.tthfanfic.org/(Story-\d+(-\d+)?(/.*)?|story.php\?no=\d+)")

    story_title_selector     = XPath(".//h2/text()")
    author_name_selector     = XPath(".//a[contains(@href, '/AuthorStories')]/text()")
    chapter_content_selector = XPath(".//a[@name='storybody']/..")
    chapter_nodes_selector   = XPath(".//select[@id='chapnav']//option")
    chapter_title_selector   = XPath(".//select[@id='chapnav']//option[@selected]/text()")
    unwanted_elements        = [CSS('h3')]
TtHScraper.register()

class FicWadScraper(Scraper):
    """A fanfic-to-ebook scraper for FicWad
    @todo: Support starting from a list page.
    """
    name             = "FicWad"
    story_url_re     = re.compile(r"http://www.ficwad.com/story/\d+")

    story_title_selector     = XPath('.//h3/*[last()]/text()')
    author_name_selector     = XPath(".//a[contains(@href, '/author/')]/text()")
    chapter_nodes_selector   = XPath(".//select[@name='goto']//option")
    chapter_title_selector   = XPath(".//select[@name='goto']//option[@selected]/text()")
    chapter_content_selector = CSS('#storytext')
FicWadScraper.register()
