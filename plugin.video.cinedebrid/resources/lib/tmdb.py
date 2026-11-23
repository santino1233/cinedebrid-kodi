# -*- coding: utf-8 -*-
"""TMDB client (v3 key or v4 read token) with a one-hour file cache."""
import requests

from . import common

API = 'https://api.themoviedb.org/3/'
IMG = 'https://image.tmdb.org/t/p/'


class TMDBError(Exception):
    pass


def get(path, **params):
    key = common.setting('tmdb_key').strip()
    if not key:
        raise TMDBError('Add your TMDB key in the add-on settings (themoviedb.org/settings/api).')
    params = {k: v for k, v in params.items() if v not in (None, '')}
    params.setdefault('language', 'en-US')
    cache_key = 'tmdb:%s?%s' % (path, '&'.join('%s=%s' % kv for kv in sorted(params.items())))

    def fetch():
        headers, q = {'accept': 'application/json'}, dict(params)
        if len(key) > 40:
            headers['Authorization'] = 'Bearer ' + key
        else:
            q['api_key'] = key
        try:
            r = requests.get(API + path, params=q, headers=headers, timeout=15)
        except requests.RequestException as e:
            raise TMDBError('Could not reach TMDB: %s' % e)
        if r.status_code == 401:
            raise TMDBError('TMDB rejected your key.')
        if r.status_code != 200:
            raise TMDBError('TMDB error %d' % r.status_code)
        return r.json()

    return common.cached(cache_key, 3600, fetch)


def poster(p, size='w500'):
    return IMG + size + p if p else ''


def fanart(p):
    return IMG + 'w1280' + p if p else ''


def genres(kind):
    return get('genre/%s/list' % kind).get('genres', [])


def listing(kind, which, page=1, **extra):
    """which: trending | popular | top_rated | now_playing | on_the_air | discover"""
    if which == 'trending':
        return get('trending/%s/week' % kind, page=page)
    if which == 'discover':
        return get('discover/%s' % kind, page=page, **extra)
    return get('%s/%s' % (kind, which), page=page)


def decade(kind, start, page=1, sort='popularity.desc'):
    d = 'primary_release_date' if kind == 'movie' else 'first_air_date'
    return get('discover/%s' % kind, page=page, sort_by=sort, **{
        d + '.gte': '%d-01-01' % start, d + '.lte': '%d-12-31' % (start + 9), 'vote_count.gte': 200})


def search(query, page=1):
    return get('search/multi', query=query, page=page, include_adult='false')


def movie(tid):
    return get('movie/%d' % tid, append_to_response='external_ids')


def show(tid):
    return get('tv/%d' % tid, append_to_response='external_ids,alternative_titles')


def season(tid, n):
    return get('tv/%d/season/%d' % (tid, n))
