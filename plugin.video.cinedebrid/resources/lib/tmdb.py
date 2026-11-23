# -*- coding: utf-8 -*-
"""TMDB client (v3 key or v4 read token): retries, a second domain, a one-hour cache and a stale-cache fallback."""
import time
from datetime import date, timedelta

import requests

from . import common

HOSTS = ('api.themoviedb.org', 'api.tmdb.org')
IMG = 'https://image.tmdb.org/t/p/'
WEEK = 7 * 86400
DNS_HINT = ('Check the device\'s internet connection. If other sites work, your router/ISP may be blocking TMDB: '
            'set the device DNS to 1.1.1.1 or 8.8.8.8 and try again.')


class TMDBError(Exception):
    pass


def _fetch(path, params, key):
    headers, q = {'accept': 'application/json'}, dict(params)
    if len(key) > 40:
        headers['Authorization'] = 'Bearer ' + key
    else:
        q['api_key'] = key
    hosts = ((common.setting('tmdb_host').strip(),) if common.setting('tmdb_host').strip() else ()) + HOSTS
    last = None
    for attempt in range(3):
        for host in hosts:
            try:
                r = requests.get('https://%s/3/%s' % (host, path), params=q, headers=headers, timeout=(6, 15))
            except requests.RequestException as e:
                last = e
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 401:
                raise TMDBError('TMDB rejected your key. Check it in the add-on settings.')
            if r.status_code == 404:
                raise TMDBError('TMDB has nothing for this (404).')
            last = 'HTTP %d' % r.status_code
        time.sleep(0.7 * (attempt + 1))
    common.log('TMDB unreachable: %s' % last)
    raise TMDBError('Could not reach TMDB. %s' % DNS_HINT)


def get(path, **params):
    key = common.setting('tmdb_key').strip()
    if not key:
        raise TMDBError('Add your TMDB key in the add-on settings (themoviedb.org/settings/api).')
    params = {k: v for k, v in params.items() if v not in (None, '')}
    params.setdefault('language', 'en-US')
    cache_key = 'tmdb:%s?%s' % (path, '&'.join('%s=%s' % kv for kv in sorted(params.items())))
    return common.cached(cache_key, 3600, lambda: _fetch(path, params, key), stale_ttl=WEEK)


def poster(p, size='w500'):
    return IMG + size + p if p else ''


def fanart(p):
    return IMG + 'w1280' + p if p else ''


def genres(kind):
    return get('genre/%s/list' % kind).get('genres', [])


def listing(kind, which, page=1):
    """which: trending | trending_day | popular | top_rated | now_playing | upcoming | on_the_air | airing_today"""
    if which == 'trending':
        return get('trending/%s/week' % kind, page=page)
    if which == 'trending_day':
        return get('trending/%s/day' % kind, page=page)
    return get('%s/%s' % (kind, which), page=page)


SORTS = {
    'popular': dict(sort_by='popularity.desc', vote_count_gte=50),
    'top': dict(sort_by='vote_average.desc', vote_count_gte=500),
    'newest': dict(sort_by='newest', vote_count_gte=15),
    'gems': dict(sort_by='vote_average.desc', vote_average_gte=7.0, vote_count_gte=150, vote_count_lte=2500),
    'acclaimed': dict(sort_by='vote_average.desc', vote_average_gte=7.8, vote_count_gte=3000),
    'grossing': dict(sort_by='revenue.desc', vote_count_gte=200),
}


def browse(kind, f, page=1):
    """Flexible discover query. f: genre, kw, company, network, y1, y2, days, lang, tvtype, sort (a SORTS key or a raw sort_by)."""
    movie = kind == 'movie'
    q = dict(SORTS.get(f.get('sort') or 'popular', dict(sort_by=f.get('sort'))))
    if q.get('sort_by') == 'newest':
        q['sort_by'] = 'primary_release_date.desc' if movie else 'first_air_date.desc'
    if q.get('sort_by') == 'revenue.desc' and not movie:
        q['sort_by'] = 'popularity.desc'
    dk = 'primary_release_date' if movie else 'first_air_date'
    today = date.today()
    if f.get('days'):
        q[dk + '.gte'] = (today - timedelta(days=int(f['days']))).isoformat()
        q[dk + '.lte'] = today.isoformat()
    else:
        if f.get('y1'):
            q[dk + '.gte'] = '%s-01-01' % f['y1']
        if f.get('y2'):
            q[dk + '.lte'] = '%s-12-31' % f['y2']
        if f.get('sort') == 'newest' and not f.get('y2'):
            q[dk + '.lte'] = today.isoformat()  # no unreleased titles in "newest"
    for src, dst in (('genre', 'with_genres'), ('kw', 'with_keywords'), ('company', 'with_companies'), ('network', 'with_networks'),
                     ('lang', 'with_original_language'), ('tvtype', 'with_type')):
        if f.get(src):
            q[dst] = f[src]
    if movie and f.get('network'):
        q.pop('with_networks', None)
    if not movie and f.get('company'):
        q.pop('with_companies', None)
    # dotted TMDB parameter names
    q = {k.replace('_gte', '.gte').replace('_lte', '.lte'): v for k, v in q.items()}
    q['include_adult'] = 'false'
    return get('discover/%s' % kind, page=page, **q)


def search(query, page=1, scope='multi'):
    return get('search/%s' % scope, query=query, page=page, include_adult='false')


def person_credits(pid):
    return get('person/%d/combined_credits' % pid)


def similar(kind, tid, page=1):
    d = get('%s/%d/recommendations' % (kind, tid), page=page)
    if not d.get('results'):
        d = get('%s/%d/similar' % (kind, tid), page=page)
    return d


def movie(tid):
    return get('movie/%d' % tid, append_to_response='external_ids')


def show(tid):
    return get('tv/%d' % tid, append_to_response='external_ids,alternative_titles')


def season(tid, n):
    return get('tv/%d/season/%d' % (tid, n))
