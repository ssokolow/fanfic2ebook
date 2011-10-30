#!/usr/bin/env python
"""
@todo: Set up automatic UPXing of extension DLLs via this recipe: http://www.py2exe.org/index.cgi/BetterCompression
@todo: Look for more modules I can exclude because they're never used: (See http://www.py2exe.org/index.cgi/FAQ)
@todo: Compare PyInstaller (http://www.pyinstaller.org/) to Py2EXE.
@todo: Design an icon to be bundled: http://www.py2exe.org/index.cgi/CustomIcons
@todo: Test against Python 3 and add "Programming Language :: Python :: 3" to the classifiers
@todo: Decide on a version scheme py2exe is OK with (http://docs.python.org/distutils/setupscript.html#additional-meta-data)
"""
import os, subprocess, sys
from distutils.core import setup
from distutils import log

def advzip(paths, description=None):
    """Wrapper for AdvanceCOMP's advzip.exe.    
    
    Assumes it will either be in the PATH or the current directory.
    """
    cmd = ['advzip', '-z4']
    desc = description or os.path.basename(paths)
    
    if isinstance(paths, basestring):
        paths = [paths]

    log.info("*** recompressing %s ***", desc)
    try:
        cmd.extend(paths)
        subprocess.call(cmd)
    except Exception, err:
        log.warn("WARNING: Failed to recompress %s:\n\t%s\nDid you put copies "
            "of advzip.exe and zlib.dll next to your setup.py?\n",
            desc, err)

def upx(paths, description=None):
    """Wrapper for upx.exe.
    
    Assumes it will either be in the PATH or the current directory.
    """
    cmd = ['upx', '--best']
    desc = description or os.path.basename(paths)
    
    if isinstance(paths, basestring):
        paths = [paths]

    log.info("*** upx-compress %s ***", desc)
    try:
        cmd.extend(paths)
        subprocess.call(cmd)
    except Exception, err:
        log.warn("WARNING: Failed to UPX-pack %s\n\t%s\n"
            "Did you put a copy of upx.exe next to your setup.py?\n", 
            desc, err)

commands = {}
try:
    import py2exe
    from py2exe.build_exe import py2exe
    
    class CompactingPy2exe(py2exe):
        """Extend py2exe to support various additional
        ways for compressing the output of the process.
        
        New py2exe options:
        - upx_internals:
          - If set to 1, UPX-pack python??.dll.
          - If set to 2, also UPX all compiled modules. 
            (Currently broken on Py27)
        - upx_results: If True, UPX resulting EXEs.
        - recompress_zip: If True, pass library.zip through AdvanceCOMP
        
        upx_internals parts borrowed from
        http://www.py2exe.org/index.cgi/BetterCompression
        
        @todo: Figure out why UPX compression of .pyd files causes crashes.
        @todo: Figure out why this suddenly is only getting called for DLLS
               and PYDs with a result of copied=0.
        """
        def initialize_options(self):
            # Add a new "upx" option for compression with upx
            py2exe.initialize_options(self)
            self.upx_internals = 0
            self.upx_exclude = []
            self.upx_results = False
            self.recompress_zip = False

        def copy_file(self, *args, **kwargs):
            # Override to UPX copied binaries.
            (fname, copied) = result = py2exe.copy_file(self, *args, **kwargs)

            basename = os.path.basename(fname)
            if (copied and self.upx_internals >= 2 and
                (basename[:6]+basename[-4:]).lower() != 'python.dll' and
                fname[-4:].lower() in ('.dll', '.pyd') and
                basename.lower() not in self.upx_exclude):
                    upx(os.path.normpath(fname))
            return result

        def create_binaries(self, *args, **kwargs):
            py2exe.create_binaries(self, *args, **kwargs)
            if self.upx_results:
                upx(self.console_exe_files +
                    self.windows_exe_files +
                    self.service_exe_files,
                    'output files')
    
        def make_lib_archive(self, *args, **kwargs):
            zip_filename = py2exe.make_lib_archive(self, *args, **kwargs)
            try:
                if self.recompress_zip:
                    advzip(os.path.normpath(zip_filename), 'library.zip')
            finally:
                return zip_filename

        def patch_python_dll_winver(self, dll_name, new_winver=None):
            # Override this to first check if the file is upx'd and skip if so
            if not self.dry_run:
                if not subprocess.call(['upx', '-qt', dll_name], 
                                       stdout=open(os.devnull, 'w')):
                    if self.verbose:
                        log.info("Skipping setting sys.winver for '%s' (UPX'd)",
                            dll_name)
                else:
                    py2exe.patch_python_dll_winver(self, dll_name, new_winver)
                    # We UPX this one file here rather than in copy_file so
                    # the version adjustment can be successful
                    if self.upx_internals >= 1:
                        upx(dll_name)
                        
    commands['py2exe'] = CompactingPy2exe
except ImportError:
    pass

sys.path.insert(0, 'src')
from fanfic2ebook import __version__

setup(name='fanfic2ebook',
    version=__version__,
    description="Fanfiction downloader/cleaner for offline reading",
    author='Stephan Sokolow',
    url='https://github.com/ssokolow/fanfic2ebook',
    license="License :: OSI Approved :: GNU General Public License (GPL)",
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
    cmdclass = commands,
    
    windows=['src/fanfic2html'],
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
            'recompress_zip': True,
            'upx_results': True,
            'upx_internals': 1,
        }
    },
    zipfile = None
)
