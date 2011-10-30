#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple fanfiction retrieval tool

Useful for generating personal archives or preparing fics to be converted to
ePub/BeBB/OEB/PDF/lit/MobiPocket/etc. for your portable eBook reader.

Features:
 - Autodetects story metadata. Requires only the URL for input.
 - Strips site templating to ensure a comfortable read on portable eBook readers.
 - Supports bundling all chapters into a single file for easy conversion.
 - Built-in support for converting to ePub, MobiPocket, and LRF via Calibre.
 - Caches retrieved pages for convenience and efficiency. (and to avoid the risk
   of getting banned by fanfiction hosts for wasting bandwidth if it gets popular)

@note: There's no inherent design trait limiting this to fanfiction.
    It's basically a generic downloader for serial web-published fiction.

@todo:
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
__version__ = "0.1pre3"
__siteurl__ = "http://github.com/ssokolow/fanfic2ebook/tree/master"

# stdlib imports
import os

import logging
log = logging.getLogger(__name__)

# Local imports
from personalities import BasePersonality
from retrieval import HTTP
from scrapers import Scraper
from writers import BaseWriter, HTMLFileWriter

# Set the User-Agent string
HTTP.set_base_UA('%s/%s +%s' % (__appname__, __version__, __siteurl__))

get_argv = lambda: []
if os.name == 'nt':
    try:
        import winui
        def get_argv():
            return winui.getLines(
                "Enter/Paste URL of fanfic to download:",
                lambda: winui.getClipboardText().encode('mbcs').strip())
    except ImportError:
        pass

def main():
    from optparse import OptionParser

    descr  = ("A simple tool for archiving fanfiction for offline reading " +
    "and converting said archives into ready-to-read eBooks for pocket " +
    "reading devices.")

    epilog = ("As an alternative to explicitly specifying a personality, " +
    "this command will alter its behaviour if called by the following names:" +
    " " + ', '.join(sorted(BasePersonality.subclasses)))

    parser = OptionParser(version="%%prog v%s" % __version__,
        usage="%prog [options] <url> ...", description=descr, epilog=epilog)
    parser.add_option('-b', '--bundle', action="store_const", dest="writer",
        default='htmldir', const=HTMLFileWriter.name, help="Also bundle the "
        "entire story into a single file with chapter headings and a table "
        "of contents.")
    parser.add_option('-t', '--target', action="store", dest="target", metavar="DIR",
        default=os.getcwd(), help="Specify a target directory other than the current working directory.")
    parser.add_option('--list-supported', action="store_true", dest="list_supported",
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
        for name, cls in (
                ('Scrapers', Scraper),
                ('Writers', BaseWriter),
                ('Personalities', BasePersonality)):
            #TODO: Merge this display mechanism into Registerable.
            print name + ":\n\t" + '\n\t'.join(sorted(x.name for x in cls.subclasses.values()))
            print
        parser.exit()

    # Provide a dialog for Windows users
    # (Note: Doesn't provide a graphical crash handler yet)
    if not args and os.name == 'nt':
        args = get_argv()

    if not args:
        parser.print_help()
        parser.exit()

    persona = BasePersonality.get(opts.persona or cmd, BasePersonality)()
    for option in persona.opts:
        setattr(opts, option, persona.opts[option])

    for url_arg in args:
        # Set up the environment and grab the fic.
        scraper = Scraper.get(url_arg)()
        writer = BaseWriter.get(opts.writer)()
        try:
            story = scraper.download_fic(url_arg)
        except Exception, err:
            log.error("Failed to retrieve story %s", url_arg)
            log.critical("TODO: Handle retrieval failures properly")
            raise
            continue

        # Create the "Story Title" folder but don't nest identical folders.
        target_dir = os.path.abspath(opts.target or os.getcwd())
        if os.path.basename(target_dir).strip().lower() == story.title.strip().lower():
            fic_target = target_dir
        else:
            fic_target = os.path.join(target_dir, writer.prepare_filename(story.title))
        writer.verify_target_dir(fic_target, create=True)

        output_path = writer.write(story, fic_target)
        persona.postproc(story, output_path, fic_target)
if __name__ == '__main__':
	main()
