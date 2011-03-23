#!/usr/bin/env python
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

   scripts=['src/fanfic2html', 'src/fanfic2lrf'],
   packages = ['fanfic2ebook'],
   package_dir = {'': 'src'},

   console=['src/fanfic2html'],
   options={
      'py2exe':
      {
         'bundle_files': 1,
         'compressed': True,
         'includes': ['lxml.etree', 'lxml._elementpath', 'gzip'],
         'optimize': 2,
      }
   },
   zipfile = None
)
