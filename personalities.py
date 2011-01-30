# -*- coding: utf-8 -*-
"""Personalities for fanfic2ebook

@todo:
 - Test the fanfic2oeb Personality and build upon it to write personalities based on
   oeb2mobi and oeb2lit.
 - Add support for passing profile flags to Calibre.
"""

__appname__ = "Fanfic Downloader for Pocket eBook Readers"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"
__version__ = "0.0pre5"

import os, subprocess

class Personality(object):
    """Defines an output mapping which can be accessed both by the -P argument
    and by alternatively-named symlinks."""
    personalities = {}              #: A class-level dict used by L{get}
    name          = 'fanfic2html'   #: The name by which the personality should be indexed.
    opts          = {}              #: A dict of changes to make to the opts

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
        cmdline = ['ebook-convert', '-t', story.title, '-a', story.author,
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
        cmdline = ['ebook-convert', '-t', story.title, '-a', story.author,
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
    """A personality for generating oeb files."""
    name  = 'fanfic2oeb'
    opts  = {'bundle' : True, 'final_ext' : '.oeb'}

    def postproc(self, story):
        """Perform the transformation from HTML to OEB."""
        story.oeb_path = os.path.splitext(story.final_path)[0] + '.opf'
        cmdline = ['ebook-convert', '--zip', '-t', story.title, '-a', story.author,
            '-o', story.oeb_path, '--publisher', story.site_name]

        if story.category:
            #FIXME: replace() commas with something else?
            cmdline.append('--subjects=%s' % story.category)
        cmdline.append(story.path)

        try:
            subprocess.check_call(cmdline)
            self.stageTwo(story)
            return True
        except subprocess.CalledProcessError:
            return False

    def stageTwo(self, story):
        """Overridden to make use of things like oeb2lit"""
        # This keeps the final extension option working in non-overridden use.
        if not os.path.splitext(story.final_path)[1].lower() == '.opf':
            os.rename(story.oeb_path, story.final_path)

# OEB support is completely untested.
#Personality.register(OEBPersonality)
