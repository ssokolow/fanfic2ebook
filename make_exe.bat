@echo off
:: Simple script for efficient EXE generation.
:: Adapted from http://www.py2exe.org/index.cgi/WinBatch
:: (And then pruned down when I got fed up debugging "The syntax of the command is incorrect")

:: Limit environment changes to this file
setlocal

:: Set paths to required commands
::TODO: Figure out how to look these up at runtime.
set SevenZipEXE="C:\Program Files\7-Zip\7z.exe"
set UpxEXE=C:\Tools\upx\upx.exe

:: Optimize ALL included code without hard-coding a path to Python.
:: http://www.py2exe.org/index.cgi/OptimizedBytecode
set PYTHONOPTIMIZE=2

::Compile the Python-Script
setup.py py2exe
if not "%errorlevel%"=="0" (
        echo Py2EXE Error!
        pause
        goto:eof
)

:: Clean out Py2EXE intermediate products
rd build /s /q

:: Recompress content with 7-Zip's Deflate engine
echo.
echo "TODO: Is it possible to UPX-pack DLL/PYDs in the bundle before recompressing with 7-zip?"
echo "TODO: Recompress content with 7-zip."
echo.
::%SevenZipEXE% -aoa x "%~dpn0_EXE\library.zip" -o"%~dpn0_EXE\library\"
::del "%~dpn0_EXE\library.zip"
::
::cd %~dpn0_EXE\library\
::%SevenZipEXE% a -tzip -mx9 "..\library.zip" -r
::cd..
::rd "%~dpn0_EXE\library" /s /q

:: Compress runtime with UPX
echo.
echo "Compressing runtime with UPX..."
echo.
cd dist\
%UpxEXE% --best *.*

:: Done
echo.
echo.
echo "Done."
echo.
