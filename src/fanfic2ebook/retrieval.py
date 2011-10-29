#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""File retrieval and caching

@todo: Consider adding ETags and If-Modified-Since support to the urllib2 fallback.
@todo: Decide where responsibility for VACUUMing should lie.
"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import logging
log = logging.getLogger(__name__)

# stdlib imports
import os, sqlite3, time, urlparse

# lxml imports
from lxml import html

OFFLINE_STORE_SCHEMA = """
PRAGMA foreign_keys=ON;

-- TODO: Decide how to eventually support multiple versions of a chapter.
CREATE TABLE IF NOT EXISTS %(prefix)surl_cache (
    id INTEGER PRIMARY KEY NOT NULL,
    url VARCHAR NOT NULL UNIQUE,
    timestamp INTEGER NOT NULL,
    contents TEXT
);
CREATE INDEX IF NOT EXISTS idx_url_cache_timestamp ON url_cache (timestamp);
"""

def get_cache_root():
    """Retrieve a cache root directory appropriate for the current platform."""
    # Portable cache directory placement
    if os.name == 'nt':
        from winpaths import get_local_appdata
        croot = get_local_appdata()
    else:
        croot = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return croot

class HTTP(object):
    """Simple wrapper which tries to use httplib2 for chapter retrieval
    and falls back to urllib2.
    """
    base_UA = 'Python HTTP cache wrapper'

    @classmethod
    def set_base_UA(cls, UA_string):
        cls.base_UA = UA_string

    @staticmethod
    def urlprep(url):
        """Prepare URLs and UNIXy paths to be used as cache keys

        @todo: I need to integrate the FFCMS URL normalizer.
        @todo: Figure out where to use pathname2url.
        """
        return urlparse.urlunparse(urlparse.urlparse(url,
            scheme='file',
            allow_fragments=False))

    def __init__(self, db_path=None, table_prefix=''):
        """
        @todo: Decide how to reconcile the httplib2 cache and the DB cache.
               (Or whether they serve purposes different enough to stay
               separate.)
        """
        self.table_prefix = table_prefix
        self.cache_root = get_cache_root()

        try:
            import httplib2
            self.cachedir = os.path.join(self.cache_root, 'httplib2_cache')
            self.http = httplib2.Http(self.cachedir)
            self.full_UA = "%s (httplib2 present. HTTP Cache enabled.)" % self.base_UA
            self.with_httplib2 = True
        except ImportError:
            import urllib2
            self.full_UA = "%s (httplib2 absent. Local cache only.)" % self.base_UA
            self.opener = urllib2.build_opener()
            self.opener.addheaders = [('User-agent', self.full_UA)]
            urllib2.install_opener(self.opener)
            self.with_httplib2 = False

        self.db_conn = sqlite3.connect(db_path or
                os.path.join(self.cache_root, 'http_permanent.sqlite3'))
        self.db_conn.executescript(OFFLINE_STORE_SCHEMA % {'prefix': table_prefix})

    def expire(self, url):
        """Flush a page from the retriever's permanent cache.
        @todo: Try to think of a way to make this less necessary given that
               Fanfiction.net returns soft 404 errors for nonexistant pages.
               ( https://secure.wikimedia.org/wikipedia/en/wiki/HTTP_404 )
        """
        self.db_conn.execute("DELETE FROM %surl_cache WHERE url = ?", [url])

    def get_dom(self, url):
        """Retrieve the given URL from the network or the cache if available.

        @todo: Figure out how to return a consistent object API so this can
               doesn't have to return a pre-parsed DOM.
        """
        row = self.db_conn.execute("SELECT contents FROM %surl_cache WHERE url = ?"
                % self.table_prefix, [url]).fetchone()

        if row:
            log.debug("Found URL in cache database: %s", url)
            return html.fromstring(row[0], base_url=url)

        if self.with_httplib2:
            log.debug("Retrieving URL using httplib2: %s", url)
            resp, content = self.http.request(url, "GET",
                    headers={"User-agent": self.full_UA})

            # Don't let errors reach the DB cache.
            if resp['status'] != '200':
                #TODO: Proper exception.
                raise Exception("Error %s while attempting to retrieve URL: %s" % (resp['status'], url))

            dom = html.fromstring(content, base_url=url)
        else:
            log.debug("Retrieving URL using urllib2: %s", url)
            dom = html.parse(self.opener.open(url)).getroot()

        self.db_conn.execute("INSERT INTO %surl_cache (url, timestamp, contents) VALUES (?, ?, ?)"
                % self.table_prefix, [url, time.time(), html.tostring(dom, encoding=unicode)])
        self.db_conn.commit()
        return dom

#TODO: Hook in a cURL-like command-line UI that's at least useful for priming the cache.
if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] <URL> ...",
            description=__doc__.replace('\r\n','\n').split('\n--snip--\n')[0])
    parser.add_option('-v', '--verbose', action="count", dest="verbose",
        default=2, help="Increase the verbosity. Can be used twice for extra effect.")
    parser.add_option('-q', '--quiet', action="count", dest="quiet",
        default=0, help="Decrease the verbosity. Can be used twice for extra effect.")
    parser.add_option('--expire', action="store_true", dest="expire",
        default=False, help="Flush the given URLs from the cache rather than "
        "retrieving them.")

    opts, args  = parser.parse_args()

    # Set up clean logging to stderr
    log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    opts.verbose = min(opts.verbose - opts.quiet, len(log_levels) - 1)
    opts.verbose = max(opts.verbose, 0)
    logging.basicConfig(level=log_levels[opts.verbose],
                        format='%(levelname)s: %(message)s')

    http = HTTP()
    for url in args:
        if opts.expire:
            http.expire(url)
        else:
            print html.tostring(http.get_dom(url))
