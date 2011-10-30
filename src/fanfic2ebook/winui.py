#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple ctypes GUI input helpers for Win32 CLI apps.

Ultra-compact for use with py2exe. (No pygtk/pywin32 deps)

For now, requires EasyDialogs, which is also very compact.
( http://www.averdevelopment.com/python/EasyDialogs.html )

Copyright (c) 2011 Stephan Sokolow (deitarion/SSokolow)

Sources used:
 - http://msdn.microsoft.com/en-us/library/windows/desktop/ms649016(v=vs.85).aspx
 - http://msdn.microsoft.com/en-us/library/windows/desktop/ms649013%28v=vs.85%29.aspx

@todo: Put this up on my GitHub Gists and blog about it.
@todo: Extend this with a minimal Windows equivalent to gtkexcepthook.

@todo:
 - Compare overhead of ctypes+EasyDialogs vs. pywin32
 - Look into making this Unicode-aware and not dependant on EasyDialogs
 - http://stackoverflow.com/questions/417004/unicode-characters-in-window-caption
 - http://www.java2s.com/Open-Source/Python/Windows/pyExcelerator/pywin32-214/win32/Demos/win32gui_dialog.py.htm
 - http://www.velocityreviews.com/forums/t334888-building-basic-dialog-in-windows.html
 - http://www.functionx.com/win32/Lesson04.htm
"""

__version__ = "0.1"

import ctypes
import EasyDialogs

#WinUser.h
CF_TEXT = 1
CF_UNICODETEXT = 13

IsClipboardFormatAvailable = ctypes.windll.user32.IsClipboardFormatAvailable
OpenClipboard = ctypes.windll.user32.OpenClipboard
CloseClipboard = ctypes.windll.user32.CloseClipboard
GetClipboardData = ctypes.windll.user32.GetClipboardData
GlobalLock = ctypes.windll.kernel32.GlobalLock
GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock

def getClipboardText():
    """Get text off the clipboard or an empty string on failure.

    @return: C{unicode} if possible, C{str} otherwise.
    @todo: Verify I'm decoding CF_TEXT correctly.
    """
    if IsClipboardFormatAvailable(CF_UNICODETEXT):
        fmt = CF_UNICODETEXT
        conv = lambda x: ctypes.c_wchar_p(x).value
    elif IsClipboardFormatAvailable(CF_TEXT):
        fmt = CF_TEXT
        conv = lambda x: ctypes.c_char_p(x).value.decode('mbcs')
    else:
        return ''

    if not OpenClipboard(None):
        return ''

    data = ''
    try:
        handle = GetClipboardData(fmt)
        data_p = GlobalLock(handle)
        data = conv(data_p)
    finally:
        GlobalUnlock(handle)
        CloseClipboard()

    return data

def getLines(prompt, default=''):
    """Display a dialog and wait for the user to respond.

    @return: A list of strings (lines) or C{None}.
    """
    if hasattr(default, '__call__'):
        default = default()

    result = EasyDialogs.AskString(prompt, default)
    return result.split('\n') if result else []

if __name__ == '__main__':
    # Test getClipboardText
    # (and demo that it's EasyDialogs that isn't Unicode-ready)
    print "\n== Clipboard contents: =="
    print getClipboardText().encode('unicode-escape').replace(r'\r\n', '\r\n')
    print "=========================\n"

    # Test getLines
    inStr = getLines(
        "It doesn't look it, but you can paste multi-line text:",
        lambda:getClipboardText().encode('mbcs').strip())
    if inStr:
        print "Received Lines:\n\t%s" % '\n\t'.join(inStr)
    else:
        print "Cancelled"
