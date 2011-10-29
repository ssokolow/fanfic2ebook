# -*- coding: utf-8 -*-
"""Post-processing mode definitions

@todo:
 - Test the fanfic2oeb Personality and build upon it to write personalities based on
   oeb2mobi and oeb2lit.
 - Add support for passing profile flags to Calibre.
"""

import os, subprocess, time

from data_structures import Registerable

class BasePersonality(Registerable):
    """Defines an output mapping which can be accessed both by the -P argument
    and by alternatively-named symlinks."""
    name          = 'fanfic2html'   #: The name by which the personality should be indexed.
    opts          = {}              #: A dict of changes to make to the opts

    def postproc(self, story, infile, outdir):
        """Override this to define post-processor behaviour."""
        pass
BasePersonality.init_registry()
BasePersonality.register()

class BaseCalibrePersonality(BasePersonality):
    """A common base class that makes adding a personality for a format
    supported by Calibre a four-line job.
    """
    opts  = {'bundle' : True}

    def make_flags(self, story):
        flags = ['--book-producer', 'fanfic2ebook',
                '--timestamp', time.ctime()]

        # FIXME: Figure out why Calibré is claiming language and creator aren't
        #        being specified when debug checks show they are.
        for flag, key in {
                '--authors': 'author',
                '--comments': 'summary',
                '--cover': 'cover',
                '--language': 'language',
                '--publisher': 'publisher',
                '--rating': 'rating',
                '--series': 'series',
                '--series-index': 'series_pos',
                '--title': 'title'}.items():
            val = getattr(story, key, None)
            if val:
                flags.extend([flag, val])

        if story.categories:
            flags.extend(['--tags',
                ','.join(x.replace(',','.') for x in story.categories)])

        pubdate = story.updated or story.published or None
        if pubdate:
            flags.extend(['--pubdate', pubdate])

        return flags

    def postproc(self, story, infile, outdir):
        """Perform the transformation from HTML to LRF."""
        infile = os.path.abspath(infile)

        if self.out_ext[0] != '.':
            self.out_ext = '.%s' % self.out_ext
        cmdline = ['ebook-convert', infile, self.out_ext] + self.make_flags(story)

        subprocess.check_call(cmdline, cwd=outdir)
        #TODO: Determine whether the following is necessary.
        # subprocess.check_call(['ebook-meta', '--category', story.categories[0]])

class BBeBPersonality(BaseCalibrePersonality):
    name  = 'fanfic2lrf'
    out_ext = '.lrf'
BBeBPersonality.register()

class EPubPersonality(BaseCalibrePersonality):
    name  = 'fanfic2epub'
    out_ext = '.epub'
EPubPersonality.register()

class MobiPersonality(BaseCalibrePersonality):
    name  = 'fanfic2mobi'
    out_ext = '.mobi'
MobiPersonality.register()
