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
 - Support custom path generation and a config file so I can automatically
   save to "~/Documents/Fanfiction/<series>/<story>/<story> - <chapter>.html"
 - I suspect it's not an encoding issue but a font issue that keeps certain
   accented characters from displaying in the Sony PRS-505. Offer an option to
   convert them to rough equivalents which can be displayed. (Common latin1
   accents like é and ï work but stuff like ō shows as whitespace) Make it default
   when the fanfic2lrf personality is active.
    - Use code from http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
    - Test with all accents I can find and provide a whitelist of ones supported by the PRS-505.
 - fanfic2lrf doesn't do a page break of you go foo</p>bar, so I need to ensure all
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
__version__ = "0.0pre6"

# stdlib imports
import os, subprocess, sys, urllib2

# Local imports
from personalities import Personality
from scrapers import Scraper

# Set the User-Agent string
_opener = urllib2.build_opener()
_opener.addheaders = [('User-agent', '%s/%s' % (__appname__, __version__))]
urllib2.install_opener(_opener)

if __name__ == '__main__':
    from optparse import OptionParser, OptionGroup

    descr  = ("A simple tool for archiving fanfiction for offline reading " +
    "and converting said archives into ready-to-read eBooks for pocket " +
    "reading devices.")

    epilog = ("As an alternative to explicitly specifying a personality, " +
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
        default=False, help="List installed scrapers and personalities.")
    parser.add_option('-P', '--personality', action="store", dest="persona", metavar="NAME",
        default=None, help="Set the personality the conversion will operate under. See --list_supported.")

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

    if opts.list_supported:
        names = sorted(Scraper.scrapers[x].site_name for x in Scraper.scrapers)
        print "Scrapers:\n\t" + '\n\t'.join(names)
        print
        print "Personalities:\n\t" + '\n\t'.join(sorted(Personality.personalities))
        sys.exit()

    if not args:
        parser.print_help()
        sys.exit()

    persona = Personality.get(opts.persona or cmd)()
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
