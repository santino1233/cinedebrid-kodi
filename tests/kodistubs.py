# -*- coding: utf-8 -*-
"""Minimal fake Kodi Python API so the add-on's logic can be exercised outside Kodi."""
import os
import sys
import tempfile
import types

PROFILE = tempfile.mkdtemp(prefix='cinedebrid-test-')
SETTINGS = {}
EVENTS = []   # everything the add-on asked Kodi to do, in order


def install():
    xbmc = types.ModuleType('xbmc')
    xbmc.LOGINFO = 1; xbmc.LOGWARNING = 2; xbmc.LOGERROR = 3
    xbmc.log = lambda m, level=1: None
    xbmc.sleep = lambda ms: None
    xbmc.executebuiltin = lambda c: EVENTS.append(('builtin', c))

    class Monitor:
        def abortRequested(self): return False
        def waitForAbort(self, t=0): return False

    class Player:
        calls = 0
        def isPlaying(self):
            Player.calls += 1
            return Player.calls % 4 != 0  # a few ticks, then playback "stops"
        def getTime(self): return 3000.0
        def getTotalTime(self): return 3300.0
    xbmc.Monitor, xbmc.Player = Monitor, Player

    xa = types.ModuleType('xbmcaddon')

    class Addon:
        def getSetting(self, k): return SETTINGS.get(k, '')
        def getAddonInfo(self, k): return {'id': 'plugin.video.cinedebrid', 'name': 'CineDebrid', 'profile': PROFILE, 'icon': 'icon.png', 'fanart': 'fanart.jpg'}.get(k, '')
        def openSettings(self): EVENTS.append(('settings',))
    xa.Addon = Addon

    xg = types.ModuleType('xbmcgui')

    class Tag:
        def __getattr__(self, name):
            return lambda *a, **k: None

    class ListItem:
        def __init__(self, label='', path=''):
            self.label, self.path, self.props = label, path, {}
        def setArt(self, a): pass
        def getVideoInfoTag(self): return Tag()
        def setProperty(self, k, v): self.props[k] = v
        def addContextMenuItems(self, m): self.menu = m

    class Dialog:
        answers = []
        def notification(self, *a, **k): EVENTS.append(('notify', a[1]))
        def ok(self, h, msg): EVENTS.append(('ok', msg))
        def input(self, *a, **k): return 'test query'
        def select(self, title, labels, **k):
            EVENTS.append(('select', title, len(labels)))
            return Dialog.answers.pop(0) if Dialog.answers else -1
        def contextmenu(self, items): return 1

    class DialogProgress:
        def create(self, *a): pass
        def update(self, *a): pass
        def iscanceled(self): return False
        def close(self): pass
    xg.ListItem, xg.Dialog, xg.DialogProgress = ListItem, Dialog, DialogProgress

    xp = types.ModuleType('xbmcplugin')
    xp.addDirectoryItem = lambda h, u, li, f: EVENTS.append(('item', li.label, f, u))
    xp.addDirectoryItems = lambda *a: None
    xp.setContent = lambda h, c: None
    xp.endOfDirectory = lambda h, **k: EVENTS.append(('end',))
    xp.setResolvedUrl = lambda h, ok, li: EVENTS.append(('resolved', ok, li.path))

    xv = types.ModuleType('xbmcvfs')
    xv.translatePath = lambda p: p

    for name, mod in (('xbmc', xbmc), ('xbmcaddon', xa), ('xbmcgui', xg), ('xbmcplugin', xp), ('xbmcvfs', xv)):
        sys.modules[name] = mod
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plugin.video.cinedebrid')
    sys.path.insert(0, os.path.abspath(root))
