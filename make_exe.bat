@echo off

:: Limit environment changes to this file
setlocal

:: Optimize ALL included code without hard-coding a path to Python.
:: http://www.py2exe.org/index.cgi/OptimizedBytecode
set PYTHONOPTIMIZE=2

::Compile the Python-Script
setup.py py2exe