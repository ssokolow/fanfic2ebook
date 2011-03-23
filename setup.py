import os, sys
if os.name != 'nt':
	print "TODO: Extend setup.py to do more than py2exe bundle-building."
	print "You may run fanfic2ebook manually from its installation directory."
	sys.exit(1)

from distutils.core import setup
import py2exe

sys.argv.append('py2exe')

setup(
	console=['fanfic2ebook.py'],
	options={
		'py2exe': 
		{
			'bundle_files': 1,
			'includes': ['lxml.etree', 'lxml._elementpath', 'gzip'],
			'optimize': 2,
		}
	},
	zipfile = None
)