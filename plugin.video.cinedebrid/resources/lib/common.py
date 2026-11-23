# -*- coding: utf-8 -*-
"""Shared helpers: settings, logging, notifications and small JSON stores in the add-on profile."""
import json
import os
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
NAME = ADDON.getAddonInfo('name')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
ICON = ADDON.getAddonInfo('icon')
os.makedirs(PROFILE, exist_ok=True)


def _seed_embedded_keys():
    """A personal build ships resources/lib/embedded.py with the owner's keys. Copy them into the add-on's
    settings once, so they survive later updates from the repository (whose package carries no keys)."""
    try:
        from . import embedded
    except ImportError:
        return
    for setting_id, value in (('tmdb_key', getattr(embedded, 'TMDB_KEY', '')), ('rd_token', getattr(embedded, 'RD_TOKEN', ''))):
        if value and not ADDON.getSetting(setting_id):
            ADDON.setSetting(setting_id, value)


_seed_embedded_keys()


def setting(key, default=''):
    v = ADDON.getSetting(key)
    return v if v != '' else default


def setting_bool(key, default=False):
    v = ADDON.getSetting(key)
    return default if v == '' else v.lower() == 'true'


def setting_int(key, default=0):
    try:
        return int(ADDON.getSetting(key))
    except (TypeError, ValueError):
        return default


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[CineDebrid] %s' % msg, level)


def notify(msg, heading=NAME, ms=4000):
    xbmcgui.Dialog().notification(heading, msg, ICON, ms)


def _path(name):
    return os.path.join(PROFILE, name)


def load(name, default):
    try:
        with open(_path(name), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save(name, data):
    tmp = _path(name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, _path(name))


def cached(name, ttl, producer):
    """File cache with a time to live: producer() runs only when the cached value is older than ttl seconds."""
    store = load('cache.json', {})
    hit = store.get(name)
    if hit and time.time() - hit['at'] < ttl:
        return hit['v']
    value = producer()
    store[name] = {'at': time.time(), 'v': value}
    if len(store) > 300:  # drop the oldest entries
        for k in sorted(store, key=lambda k: store[k]['at'])[:100]:
            store.pop(k, None)
    try:
        save('cache.json', store)
    except Exception:
        pass
    return value
