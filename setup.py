import os
from distutils.core import setup

try:
	import py2exe
except ImportError:
	pass

setup(
	scripts=['src/fanfic2html', 'src/fanfic2lrf'],
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
	packages = ['fanfic2ebook'],
	package_dir = {'': 'src'},
	zipfile = None
)