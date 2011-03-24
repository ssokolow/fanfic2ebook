#!/usr/bin/env python
"""
@todo: Design an icon to be bundled: http://www.py2exe.org/index.cgi/CustomIcons
@todo: Test against Python 3 and add "Programming Language :: Python :: 3" to the classifiers
@todo: Decide on a version scheme py2exe is OK with (http://docs.python.org/distutils/setupscript.html#additional-meta-data)
"""
import sys
from distutils.core import setup

try:
   import py2exe
except ImportError:
   pass

sys.path.insert(0, 'src')
from fanfic2ebook import __version__

setup(name='fanfic2ebook',
    version=__version__,
    description="Fanfiction downloader/cleaner for offline reading",
    author='Stephan Sokolow',
    url='https://github.com/ssokolow/fanfic2ebook',
    classifiers = [
        "Programming Language :: Python",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        #TODO: Figure out other peoples' understanding of "Development Status"
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: System :: Archiving",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Markup :: HTML"
    ],

    scripts=['src/fanfic2html', 'src/fanfic2lrf'],
    packages = ['fanfic2ebook'],
    package_dir = {'': 'src'},

    console=['src/fanfic2html'],
    options={
        'py2exe':
        {
            'bundle_files': 1,
            'compressed': True,
            'excludes': [
                'calendar', 'difflib', 'email', 'ftplib',
                'pdb', 'pyreadline', 'select', 'ssl', '_ssl',
                'unittest', 'uu', 'webbrowser'
            ],
            'includes': ['lxml.etree', 'lxml._elementpath', 'gzip'],
            'optimize': 2,
        }
    },
    zipfile = None
)
