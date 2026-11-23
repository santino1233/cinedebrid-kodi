# -*- coding: utf-8 -*-
"""Real-Debrid REST client: add a torrent by infohash, pick the file, wait, unrestrict."""
import time

import requests

from . import common
from .pick import pick_file

BASE = 'https://api.real-debrid.com/rest/1.0/'
DEAD = ('error', 'magnet_error', 'virus', 'dead')
MESSAGES = {
    8: 'Real-Debrid token is invalid. Update it in the add-on settings.',
    9: 'Real-Debrid premium has expired.',
    20: 'Real-Debrid premium is required.',
    21: 'Too many active downloads on Real-Debrid.',
    34: 'Real-Debrid is rate-limiting requests. Wait a minute and try again.',
    35: 'Real-Debrid refuses this release (flagged as infringing).',
}


class RDError(Exception):
    def __init__(self, msg, blocked=False, fatal=False):
        super().__init__(msg)
        self.blocked = blocked
        self.fatal = fatal


def token():
    t = common.setting('rd_token').strip()
    if not t:
        raise RDError('Add your Real-Debrid API token in the add-on settings (real-debrid.com/apitoken).', fatal=True)
    return t


def call(method, path, data=None):
    try:
        r = requests.request(method, BASE + path, data=data, headers={'Authorization': 'Bearer ' + token()}, timeout=20)
    except requests.RequestException as e:
        raise RDError('Could not reach Real-Debrid: %s' % e, fatal=True)
    if r.status_code in (200, 201, 202, 204):
        try:
            return r.json() if r.text else {}
        except ValueError:
            return {}
    try:
        body = r.json()
    except ValueError:
        body = {}
    code = body.get('error_code')
    msg = MESSAGES.get(code) or 'Real-Debrid: %s' % (body.get('error') or 'HTTP %d' % r.status_code)
    raise RDError(msg, blocked=(code == 35 or r.status_code == 451), fatal=code in (8, 9, 20, 21, 34) or r.status_code == 401)


def account():
    u = call('GET', 'user')
    return u


BLOCK_HOURS = 2  # short on purpose: a temporary account-wide refusal must not poison the list


def _blocklist():
    now = time.time()
    data = {h: t for h, t in common.load('blocked.json', {}).items() if now - t < BLOCK_HOURS * 3600}
    return data


def is_blocked(h):
    return h.lower() in _blocklist()


def _mark_blocked(h):
    data = _blocklist()
    data[h.lower()] = time.time()
    common.save('blocked.json', data)


def _delete(tid):
    try:
        call('DELETE', 'torrents/delete/' + tid)
    except RDError:
        pass


def start(hash_, season=None, episode=None):
    """Make sure the torrent is on the account with the wanted file selected. Returns (torrent_id, created)."""
    hash_ = hash_.lower()
    if is_blocked(hash_):
        raise RDError(MESSAGES[35], blocked=True)
    for t in call('GET', 'torrents?limit=500') or []:
        if (t.get('hash') or '').lower() != hash_ or t.get('status') in DEAD:
            continue
        info = call('GET', 'torrents/info/' + t['id'])
        if info.get('status') == 'waiting_files_selection':
            return t['id'], False
        try:
            pick_file([f for f in info.get('files', []) if f.get('selected')], season, episode)
            return t['id'], False
        except LookupError:
            continue  # that copy has other episodes selected
    try:
        tid = call('POST', 'torrents/addMagnet', {'magnet': 'magnet:?xt=urn:btih:' + hash_})['id']
    except RDError as e:
        if e.blocked:
            _mark_blocked(hash_)
        raise
    return tid, True


def wait_ready(tid, season=None, episode=None, seconds=8, progress=None):
    """Poll until the torrent is downloaded. progress(info) is called each tick and may return True to cancel.
    Returns the final info dict (check info['status'] == 'downloaded')."""
    end = time.time() + seconds
    selected = False
    info = {}
    while True:
        info = call('GET', 'torrents/info/' + tid)
        st = info.get('status')
        if st in DEAD:
            raise RDError('Real-Debrid could not fetch this torrent (%s).' % st)
        if st == 'waiting_files_selection' and not selected:
            f = pick_file(info.get('files', []), season, episode)
            call('POST', 'torrents/selectFiles/' + tid, {'files': str(f['id'])})
            selected = True
            continue
        if st == 'downloaded':
            return info
        if progress and progress(info):
            return info
        if time.time() > end:
            return info
        time.sleep(1.0 if seconds <= 12 else 3.0)


def stream_url(info, season=None, episode=None):
    selected = [f for f in info.get('files', []) if f.get('selected')]
    f = pick_file(selected, season, episode)
    links = info.get('links') or []
    link = links[selected.index(f)] if selected.index(f) < len(links) else (links[0] if links else None)
    if not link:
        raise RDError('Real-Debrid returned no link for this file.')
    u = call('POST', 'unrestrict/link', {'link': link})
    return u['download'], u.get('filename') or f['path'].split('/')[-1]


def discard(tid):
    _delete(tid)
