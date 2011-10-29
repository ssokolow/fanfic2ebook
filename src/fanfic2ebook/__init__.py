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

@note: There's no inherent design trait limiting this to fanfiction.
    It's basically a generic downloader for serial web-published fiction.

@todo:
 - Support transparently resuming from gzip/bzip2-compressed save sets.
 - Support custom path generation and a config file so I can automatically
   save to "~/Documents/Fanfiction/<series>/<story>/<story> - <chapter>.html"
 - I suspect it's not an encoding issue but a font issue that keeps certain
   accented characters from displaying in the Sony PRS-505. Offer an option to
   convert them to rough equivalents which can be displayed. (Common latin1
   accents like é and ï work but stuff like ō shows as whitespace) Make it default
   when the fanfic2lrf personality is active.
    - Use code from http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
    - Test with all accents I can find and provide a whitelist of ones supported by the PRS-505.
 - fanfic2lrf doesn't do a line break if you go foo</p>bar, so I need to ensure all
   text is in paragraph elements or equivalent.
 - Finish re-architecting this so it meets my non-drowsy standards.
   (eg. passing arbitrary flags to html2lrf)
 - Test latest Calibré to see if the </p> and accent handling in html2lrf are fixed.
   (If not, file a bug report and share the code I used to work around the problem)

@newfield appname: Application Name
"""

__appname__ = "Fanfic Downloader for Pocket eBook Readers"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"
__version__ = "0.1pre2"
__siteurl__ = "http://github.com/ssokolow/fanfic2ebook/tree/master"

# stdlib imports
import os, subprocess

import logging
log = logging.getLogger(__name__)

# Local imports
from personalities import Personality
from retrieval import HTTP
from scrapers import Scraper
from writers import Writer

# Set the User-Agent string
HTTP.set_base_UA('%s/%s +%s' % (__appname__, __version__, __siteurl__))

def main():
    from optparse import OptionParser, OptionGroup

    descr  = ("A simple tool for archiving fanfiction for offline reading " +
    "and converting said archives into ready-to-read eBooks for pocket " +
    "reading devices.")

    epilog = ("As an alternative to explicitly specifying a personality, " +
    "this command will alter its behaviour if called by the following names:" +
    " " + ', '.join(sorted(Personality.personalities)))

    parser = OptionParser(version="%%prog v%s" % __version__,
        usage="%prog [options] <url> ...", description=descr, epilog=epilog)
    parser.add_option('-b', '--bundle', action="store", dest="writer",
        default='htmldir', value='htmlfile', help="Also bundle the entire "
        "story into a single file with chapter headings and a table of contents.")
    parser.add_option('-t', '--target', action="store", dest="target", metavar="DIR",
        default=os.getcwd(), help="Specify a target directory other than the current working directory.")
    parser.add_option('--list_supported', action="store_true", dest="list_supported",
        default=False, help="List installed scrapers and personalities.")
    parser.add_option('-P', '--personality', action="store", dest="persona", metavar="NAME",
        default=None, help="Set the personality the conversion will operate under. See --list_supported.")
    parser.add_option('-v', '--verbose', action="count", dest="verbose",
        default=2, help="Increase the verbosity. Can be used twice for extra effect.")
    parser.add_option('-q', '--quiet', action="count", dest="quiet",
        default=0, help="Decrease the verbosity. Can be used twice for extra effect.")

    #pre_group = OptionGroup(parser, "Pre-Processing Options")
    #pre_group.add_option('--strip-accents', action="store_true", dest="strip_accents",
    #    default=False, help="Remove diacritics for compatibility with readers with " +
    #    "limited fonts and no internal fallback mechanism. (eg. Sony PRS-505)")

    pp_group = OptionGroup(parser, "Post-Processing Options")
    pp_group.add_option('-p', '--postproc', action="append", dest="postproc", metavar="CMD",
        default=[], help="Call the specified post-processor after each retrieval " +
                         "completes. Can be used multiple times. Implies --bundle.")
    pp_group.add_option('-e', '--final_ext', action="store", dest="final_ext", metavar="EXT",
        default='.out', help="Set the extension to be used in the output filename " +
                           "available to post-processor templates.")
    parser.add_option_group(pp_group)

    opts, args = parser.parse_args()
    cmd = parser.get_prog_name()

    # Set up clean logging to stderr
    log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    opts.verbose = min(opts.verbose - opts.quiet, len(log_levels) - 1)
    opts.verbose = max(opts.verbose, 0)
    logging.basicConfig(level=log_levels[opts.verbose],
                        format='%(levelname)s: %(message)s')

    if opts.list_supported:
        names = sorted(Scraper.scrapers[x].site_name for x in Scraper.scrapers)
        print "Scrapers:\n\t" + '\n\t'.join(names)
        print
        print "Personalities:\n\t" + '\n\t'.join(sorted(Personality.personalities))
        parser.exit()

    if not args:
        parser.print_help()
        parser.exit()

    persona = Personality.get(opts.persona or cmd, True)()
    for option in persona.opts:
        setattr(opts, option, persona.opts[option])

    if opts.postproc:
        opts.bundle = True

    for url_arg in args:
        # Set up the environment and grab the fic.
        scraper = Scraper.get(url_arg)(opts.final_ext)
        writer = Writer.get(opts.writer)
        try:
            story = scraper.download_fic(url_arg)
        except Exception, err:
            log.error("Failed to retrieve story %s", url_arg)
            log.critical("TODO: Handle retrieval failures properly")
            continue

        # Create the "Story Title" folder but don't nest identical folders.
        target_dir = os.path.abspath(opts.target or os.getcwd())
        if os.path.basename(target_dir).strip().lower() == story.title.strip().lower():
            fic_target = target_dir
        else:
            fic_target = os.path.join(target_dir, writer.prepare_filename(story.title))
        writer.verify_target_dir(fic_target, create=True)

        writer.write(story, fic_target)

        #    story.final_path = os.path.join(fic_target,
        #        '%s.%s' % (self.prepare_filename(story.title), self.final_ext.lstrip('.')))
        persona.postproc(story)

        if opts.postproc:
            inputs = {
                'appname'   : "%s v%s" % (__appname__, __version__),
                'author'    : story.author,
                'bundle'    : story.path,
                'category'  : story.category,
                'coverfile' : story.cover,
                'outfile'   : story.final_path,
                'site_name' : story.site_name,
                'title'     : story.title
            }

            for pp_cmdline in opts.postproc:
                cmdlist = pp_cmdline.strip().split()
                print "Calling post-processor: %s" % cmdlist[0]
                subprocess.call([r % inputs for r in cmdlist])

if __name__ == '__main__':
	main()
