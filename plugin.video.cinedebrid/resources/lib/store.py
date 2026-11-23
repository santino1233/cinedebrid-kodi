# -*- coding: utf-8 -*-
"""Continue Watching, watched marks and My List, kept as small JSON files in the add-on profile."""
import time

from . import common

CW = 'continue.json'
LIST = 'mylist.json'


def key(kind, tmdb_id, season=None, episode=None):
    return 'm%s' % tmdb_id if kind == 'movie' else 'e%s:%s:%s' % (tmdb_id, season, episode)


def get_progress(k):
    return common.load(CW, {}).get(k)


def save_progress(kind, tmdb_id, season, episode, info, pos, total):
    data = common.load(CW, {})
    data[key(kind, tmdb_id, season, episode)] = {
        'kind': kind, 'tmdb': tmdb_id, 'season': season, 'episode': episode, 'title': info.get('show') or info.get('title'),
        'sub': info.get('episode_name') or '', 'poster': info.get('poster'), 'fanart': info.get('fanart'),
        'pos': pos, 'total': total, 'ts': time.time(), 'next': False}
    common.save(CW, data)


def finished(kind, tmdb_id, season, episode, info):
    """Fully watched: mark it, drop it from Continue Watching and queue 'up next' for a following episode."""
    data = common.load(CW, {})
    k = key(kind, tmdb_id, season, episode)
    data.pop(k, None)
    watched = common.load('watched.json', [])
    if k not in watched:
        watched.append(k)
        common.save('watched.json', watched)
    if kind == 'episode':
        nxt = _next_episode(tmdb_id, season, episode)
        if nxt:
            ns, ne, name = nxt
            data[key('episode', tmdb_id, ns, ne)] = {
                'kind': 'episode', 'tmdb': tmdb_id, 'season': ns, 'episode': ne, 'title': info.get('show'), 'sub': name,
                'poster': info.get('poster'), 'fanart': info.get('fanart'), 'pos': 0, 'total': 0, 'ts': time.time(), 'next': True}
    common.save(CW, data)


def _next_episode(tmdb_id, season, episode):
    from . import tmdb
    try:
        eps = tmdb.season(tmdb_id, season).get('episodes', [])
        for e in eps:
            if e.get('episode_number') == episode + 1:
                return season, episode + 1, e.get('name') or ''
        nxt = tmdb.season(tmdb_id, season + 1).get('episodes', [])
        if nxt:
            return season + 1, nxt[0].get('episode_number', 1), nxt[0].get('name') or ''
    except Exception:
        pass
    return None


def continue_items():
    """Most recent entry per show/movie, newest first. Skips nearly-finished ones."""
    seen, out = set(), []
    for v in sorted(common.load(CW, {}).values(), key=lambda v: v['ts'], reverse=True):
        if not v.get('next') and v.get('total') and v['pos'] / v['total'] >= 0.93:
            continue
        ident = (v['kind'], v['tmdb'] if v['kind'] == 'movie' else v['tmdb'])
        if ident in seen:
            continue
        seen.add(ident)
        out.append(v)
    return out


def remove_progress(k):
    data = common.load(CW, {})
    if data.pop(k, None) is not None:
        common.save(CW, data)


def is_watched(k):
    return k in common.load('watched.json', [])


# ---- My List
def mylist():
    return common.load(LIST, [])


def in_list(kind, tmdb_id):
    return any(x['kind'] == kind and x['id'] == tmdb_id for x in mylist())


def add_to_list(kind, tmdb_id, title, poster):
    items = mylist()
    if not in_list(kind, tmdb_id):
        items.insert(0, {'kind': kind, 'id': tmdb_id, 'title': title, 'poster': poster})
        common.save(LIST, items)


def remove_from_list(kind, tmdb_id):
    common.save(LIST, [x for x in mylist() if not (x['kind'] == kind and x['id'] == tmdb_id)])
