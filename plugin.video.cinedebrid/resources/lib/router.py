# -*- coding: utf-8 -*-
"""Menus and routing."""
import sys
from urllib.parse import urlencode, parse_qsl

import xbmcgui
import xbmcplugin

from . import common, rd, store, tmdb

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE = 'plugin://%s/' % common.ADDON_ID


def url(**kw):
    return BASE + '?' + urlencode({k: v for k, v in kw.items() if v is not None})


def folder(label, art=None, plot='', **kw):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': common.ICON, 'thumb': art or common.ICON, 'poster': art or common.ICON, 'fanart': common.ADDON.getAddonInfo('fanart')})
    if plot:
        li.getVideoInfoTag().setPlot(plot)
    xbmcplugin.addDirectoryItem(HANDLE, url(**kw), li, True)


def end(content=None, cache=True):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)


# ------------------------------------------------------------------ root
def root(_p):
    if store.continue_items():
        folder('Continue Watching', action='continue')
    folder('Movies', action='menu', kind='movie')
    folder('TV Shows', action='menu', kind='tv')
    folder('My List', action='mylist')
    folder('Search', action='search')
    folder('Settings', action='settings')
    end(cache=False)


def menu(p):
    kind = p['kind']
    rows = [('Trending', 'trending'), ('Popular', 'popular'), ('Top Rated', 'top_rated'),
            ('Now Playing' if kind == 'movie' else 'On The Air', 'now_playing' if kind == 'movie' else 'on_the_air')]
    for label, which in rows:
        folder(label, action='list', kind=kind, which=which, page=1)
    folder('Genres', action='genres', kind=kind)
    folder('By Decade', action='decades', kind=kind)
    end()


def genres(p):
    for g in tmdb.genres(p['kind']):
        folder(g['name'], action='genre', kind=p['kind'], id=g['id'], page=1)
    end()


def decades(p):
    for start in range(2020, 1949, -10):
        folder("%ds" % start, action='decade', kind=p['kind'], start=start, page=1)
    end()


# ------------------------------------------------------------------ item lists
def _year(r):
    return (r.get('release_date') or r.get('first_air_date') or '')[:4]


def title_item(kind, r, from_search=False):
    """One movie (playable) or show (folder) from a TMDB result."""
    tid = r['id']
    name = r.get('title') or r.get('name') or '?'
    year = _year(r)
    poster = tmdb.poster(r.get('poster_path'))
    li = xbmcgui.ListItem('%s (%s)' % (name, year) if year else name)
    li.setArt({'poster': poster, 'thumb': poster, 'icon': poster, 'fanart': tmdb.fanart(r.get('backdrop_path'))})
    tag = li.getVideoInfoTag()
    tag.setTitle(name)
    tag.setPlot(r.get('overview') or '')
    tag.setMediaType('movie' if kind == 'movie' else 'tvshow')
    if year.isdigit():
        tag.setYear(int(year))
    if r.get('vote_average'):
        tag.setRating(float(r['vote_average']))
    menu = []
    if store.in_list(kind, tid):
        menu.append(('Remove from My List', 'RunPlugin(%s)' % url(action='unlist', kind=kind, id=tid)))
    else:
        menu.append(('Add to My List', 'RunPlugin(%s)' % url(action='tolist', kind=kind, id=tid, title=name, poster=poster)))
    if kind == 'movie':
        k = store.key('movie', tid)
        if store.is_watched(k):
            tag.setPlaycount(1)
        li.setProperty('IsPlayable', 'true')
        menu.append(('Choose source…', 'PlayMedia(%s)' % url(action='play', kind='movie', id=tid, ask=1)))
        li.addContextMenuItems(menu)
        xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='movie', id=tid), li, False)
    else:
        li.addContextMenuItems(menu)
        xbmcplugin.addDirectoryItem(HANDLE, url(action='seasons', id=tid, name=name), li, True)


def results(kind, data, nextargs):
    for r in data.get('results', []):
        k = kind
        if kind == 'multi':
            k = r.get('media_type')
            if k not in ('movie', 'tv'):
                continue
        title_item(k, r)
    if data.get('page', 1) < min(data.get('total_pages', 1), 50):
        folder('Next page ›', **dict(nextargs, page=data['page'] + 1))
    end('movies' if kind == 'movie' else 'tvshows')


def list_(p):
    page = int(p.get('page', 1))
    results(p['kind'], tmdb.listing(p['kind'], p['which'], page), dict(action='list', kind=p['kind'], which=p['which']))


def genre(p):
    page = int(p.get('page', 1))
    results(p['kind'], tmdb.listing(p['kind'], 'discover', page, with_genres=p['id'], sort_by='popularity.desc', **{'vote_count.gte': 100}),
            dict(action='genre', kind=p['kind'], id=p['id']))


def decade(p):
    page = int(p.get('page', 1))
    results(p['kind'], tmdb.decade(p['kind'], int(p['start']), page), dict(action='decade', kind=p['kind'], start=p['start']))


def search(p):
    q = p.get('q') or xbmcgui.Dialog().input('Search movies and TV shows')
    if not q:
        return end()
    page = int(p.get('page', 1))
    results('multi', tmdb.search(q, page), dict(action='search', q=q))


# ------------------------------------------------------------------ TV drill-down
def seasons(p):
    tid = int(p['id'])
    s = tmdb.show(tid)
    for se in s.get('seasons', []):
        n = se['season_number']
        if n == 0 and not se.get('episode_count'):
            continue
        li = xbmcgui.ListItem('Season %d' % n if n else 'Specials')
        poster = tmdb.poster(se.get('poster_path') or s.get('poster_path'))
        li.setArt({'poster': poster, 'thumb': poster, 'fanart': tmdb.fanart(s.get('backdrop_path'))})
        tag = li.getVideoInfoTag()
        tag.setMediaType('season')
        tag.setPlot(se.get('overview') or s.get('overview') or '')
        xbmcplugin.addDirectoryItem(HANDLE, url(action='episodes', id=tid, season=n), li, True)
    end('seasons')


def episodes(p):
    tid, n = int(p['id']), int(p['season'])
    s = tmdb.show(tid)
    for e in tmdb.season(tid, n).get('episodes', []):
        num = e['episode_number']
        li = xbmcgui.ListItem('%d. %s' % (num, e.get('name') or 'Episode %d' % num))
        still = tmdb.poster(e.get('still_path'), 'w780')
        li.setArt({'thumb': still, 'poster': tmdb.poster(s.get('poster_path')), 'fanart': tmdb.fanart(s.get('backdrop_path'))})
        tag = li.getVideoInfoTag()
        tag.setTitle(e.get('name') or '')
        tag.setPlot(e.get('overview') or '')
        tag.setMediaType('episode')
        tag.setSeason(n)
        tag.setEpisode(num)
        tag.setTvShowTitle(s.get('name') or '')
        if e.get('air_date'):
            tag.setFirstAired(e['air_date'])
        if e.get('vote_average'):
            tag.setRating(float(e['vote_average']))
        if store.is_watched(store.key('episode', tid, n, num)):
            tag.setPlaycount(1)
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems([('Choose source…', 'PlayMedia(%s)' % url(action='play', kind='episode', id=tid, season=n, episode=num, ask=1))])
        xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='episode', id=tid, season=n, episode=num), li, False)
    end('episodes')


# ------------------------------------------------------------------ continue / my list
def continue_(_p):
    for v in store.continue_items():
        sub = ''
        if v['kind'] == 'episode':
            sub = ' · S%02dE%02d%s' % (v['season'], v['episode'], ' ' + v['sub'] if v.get('sub') else '')
        if v.get('next'):
            label = '%s%s  [COLOR lime](up next)[/COLOR]' % (v['title'], sub)
        elif v.get('total'):
            left = int((v['total'] - v['pos']) / 60)
            label = '%s%s  [COLOR grey](%d min left)[/COLOR]' % (v['title'], sub, left)
        else:
            label = v['title'] + sub
        li = xbmcgui.ListItem(label)
        li.setArt({'poster': v.get('poster') or '', 'thumb': v.get('poster') or '', 'fanart': v.get('fanart') or ''})
        li.getVideoInfoTag().setMediaType('movie' if v['kind'] == 'movie' else 'episode')
        li.setProperty('IsPlayable', 'true')
        k = store.key(v['kind'], v['tmdb'], v.get('season'), v.get('episode'))
        li.addContextMenuItems([('Remove from Continue Watching', 'RunPlugin(%s)' % url(action='cw_remove', key=k))])
        xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind=v['kind'], id=v['tmdb'], season=v.get('season'), episode=v.get('episode')), li, False)
    end('videos', cache=False)


def mylist(_p):
    for x in store.mylist():
        r = {'id': x['id'], 'title': x['title'], 'name': x['title']}
        li_poster = x.get('poster') or ''
        li = xbmcgui.ListItem(x['title'])
        li.setArt({'poster': li_poster, 'thumb': li_poster})
        li.addContextMenuItems([('Remove from My List', 'RunPlugin(%s)' % url(action='unlist', kind=x['kind'], id=x['id']))])
        if x['kind'] == 'movie':
            li.setProperty('IsPlayable', 'true')
            li.getVideoInfoTag().setMediaType('movie')
            xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='movie', id=x['id']), li, False)
        else:
            li.getVideoInfoTag().setMediaType('tvshow')
            xbmcplugin.addDirectoryItem(HANDLE, url(action='seasons', id=x['id'], name=x['title']), li, True)
    end('videos', cache=False)


def tolist(p):
    store.add_to_list(p['kind'], int(p['id']), p.get('title', ''), p.get('poster', ''))
    common.notify('Added to My List')


def unlist(p):
    store.remove_from_list(p['kind'], int(p['id']))
    common.notify('Removed from My List')
    import xbmc
    xbmc.executebuiltin('Container.Refresh')


def cw_remove(p):
    store.remove_progress(p['key'])
    import xbmc
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------------ misc
def check_accounts(_p):
    lines = []
    try:
        u = rd.account()
        lines.append('Real-Debrid: %s (%s) until %s' % (u.get('username'), u.get('type'), (u.get('expiration') or '')[:10]))
    except Exception as e:
        lines.append('Real-Debrid: %s' % e)
    try:
        tmdb.get('configuration')
        lines.append('TMDB: key works')
    except Exception as e:
        lines.append('TMDB: %s' % e)
    try:
        from cocoscrapers import sources as coco
        names = [n for n, _ in coco()]
        lines.append('CocoScrapers: %d providers enabled (%s)' % (len(names), ', '.join(names[:8]) + ('…' if len(names) > 8 else '')))
    except Exception as e:
        lines.append('CocoScrapers: not available (%s)' % e)
    xbmcgui.Dialog().ok(common.NAME, '\n'.join(lines))


def settings(_p):
    common.ADDON.openSettings()


def dispatch(argv):
    from . import player
    params = dict(parse_qsl(argv[2][1:])) if len(argv) > 2 else {}
    action = params.get('action', 'root')
    if action == 'play':
        return player.play(HANDLE, params['kind'], int(params['id']),
                           int(params['season']) if params.get('season') not in (None, '', 'None') else None,
                           int(params['episode']) if params.get('episode') not in (None, '', 'None') else None,
                           ask=params.get('ask') == '1')
    routes = {
        'root': root, 'menu': menu, 'genres': genres, 'decades': decades, 'list': list_, 'genre': genre, 'decade': decade,
        'search': search, 'seasons': seasons, 'episodes': episodes, 'continue': continue_, 'mylist': mylist,
        'tolist': tolist, 'unlist': unlist, 'cw_remove': cw_remove, 'check_accounts': check_accounts, 'settings': settings,
    }
    try:
        routes.get(action, root)(params)
    except tmdb.TMDBError as e:
        xbmcgui.Dialog().ok(common.NAME, str(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
