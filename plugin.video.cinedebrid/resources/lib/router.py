# -*- coding: utf-8 -*-
"""Menus and routing. Everything that lists titles ends up in `results()` so posters are the default view."""
import sys
from datetime import date
from urllib.parse import urlencode, parse_qsl

import xbmc
import xbmcgui
import xbmcplugin

from . import common, rd, store, tmdb

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE = 'plugin://%s/' % common.ADDON_ID
FILTER_KEYS = ('genre', 'kw', 'company', 'network', 'y1', 'y2', 'days', 'lang', 'tvtype')

# Kodi skins number their views. Poster / wall / list ids for the common skins; anything else can be set by hand in settings.
SKIN_VIEWS = {
    'skin.estuary': {'poster': 51, 'wall': 500, 'list': 50},
    'skin.estuary.modv2': {'poster': 51, 'wall': 500, 'list': 50},
    'skin.estuary.mod': {'poster': 51, 'wall': 500, 'list': 50},
}

NETWORKS = [('Netflix', 213), ('HBO', 49), ('Prime Video', 1024), ('Disney+', 2739), ('Apple TV', 2552), ('Hulu', 453),
            ('Paramount+', 4330), ('Showtime', 67), ('AMC', 174), ('FX', 88)]
STUDIOS = [('Marvel Studios', 420), ('Pixar', 3), ('Walt Disney Pictures', 2), ('Warner Bros.', 174), ('Universal', 33),
           ('Paramount', 4), ('Columbia', 5), ('Lucasfilm', 1), ('DC', 9993), ('A24', 41077), ('Lionsgate', 1632), ('Legendary', 923)]
THEMES = [('Superhero', 9715), ('Based on a True Story', 9672), ('Heist', 10051), ('Time Travel', 4379), ('Zombies', 12377),
          ('Dystopia', 4565), ('Post-Apocalyptic', 359337), ('Serial Killer', 10714), ('Martial Arts', 779), ('Spy', 470),
          ('Courtroom', 33519), ('Space', 9882)]
SORT_LABELS = [('popular', 'Popular'), ('top', 'Top Rated'), ('newest', 'Newest First'), ('gems', 'Hidden Gems')]


def url(**kw):
    return BASE + '?' + urlencode({k: v for k, v in kw.items() if v not in (None, '')})


def folder(label, art=None, plot='', **kw):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': art or common.ICON, 'thumb': art or common.ICON, 'poster': art or common.ICON,
               'fanart': common.ADDON.getAddonInfo('fanart')})
    if plot:
        li.getVideoInfoTag().setPlot(plot)
    xbmcplugin.addDirectoryItem(HANDLE, url(**kw), li, True)


def apply_view():
    mode = common.setting('view_mode', 'poster')
    if mode == 'skin':
        return
    vid = common.setting_int('view_custom', 0) or SKIN_VIEWS.get(xbmc.getSkinDir(), {}).get(mode)
    if vid:
        xbmc.sleep(120)
        xbmc.executebuiltin('Container.SetViewMode(%d)' % vid)


def end(content=None, cache=True, view=False):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)
    if view:
        apply_view()


# ------------------------------------------------------------------ top menus
def root(_p):
    if store.continue_items():
        folder('Continue Watching', action='continue')
    folder('Movies', action='menu', kind='movie')
    folder('TV Shows', action='menu', kind='tv')
    folder('Search', action='search_menu')
    folder('My List', action='mylist')
    folder('Tools & Settings', action='tools')
    end(cache=False)


def menu(p):
    kind = p['kind']
    movie = kind == 'movie'
    folder('Trending This Week', action='list', kind=kind, which='trending', page=1)
    folder('Trending Today', action='list', kind=kind, which='trending_day', page=1)
    folder('Popular', action='list', kind=kind, which='popular', page=1)
    folder('Top Rated', action='list', kind=kind, which='top_rated', page=1)
    if movie:
        folder('Now Playing', action='list', kind=kind, which='now_playing', page=1)
        folder('Upcoming', action='list', kind=kind, which='upcoming', page=1)
    else:
        folder('On The Air', action='list', kind=kind, which='on_the_air', page=1)
        folder('Airing Today', action='list', kind=kind, which='airing_today', page=1)
    folder('New Releases (last 90 days)' if movie else 'New Shows (last 90 days)', action='browse', kind=kind, sort='newest', days=90, page=1)
    folder('Genres', action='genres', kind=kind)
    folder('Years & Decades', action='years', kind=kind)
    folder('Themes & Collections', action='themes', kind=kind)
    folder('Studios' if movie else 'Networks & Streaming', action='studios' if movie else 'networks', kind=kind)
    folder('Critically Acclaimed', action='browse', kind=kind, sort='acclaimed', page=1)
    folder('Hidden Gems', action='browse', kind=kind, sort='gems', page=1)
    if movie:
        folder('Box Office Hits', action='browse', kind=kind, sort='grossing', page=1)
        folder('Family', action='sorts', kind=kind, genre=10751)
    else:
        folder('Mini-Series', action='sorts', kind=kind, tvtype=2)
        folder('Documentary Series', action='sorts', kind=kind, genre=99)
        folder('Reality', action='sorts', kind=kind, genre=10764)
        folder('Anime', action='sorts', kind=kind, genre=16, lang='ja')
        folder('Kids', action='sorts', kind=kind, genre=10762)
    folder('Search ' + ('Movies' if movie else 'TV Shows'), action='search', scope=kind)
    end()


def sorts(p):
    """The four ways to sort whatever filter was chosen (genre, decade, studio...)."""
    kind = p['kind']
    keep = {k: p[k] for k in FILTER_KEYS if p.get(k)}
    for key, label in SORT_LABELS:
        folder(label, action='browse', kind=kind, sort=key, page=1, **keep)
    end()


def _sorts_entry(label, kind, **flt):
    folder(label, action='sorts', kind=kind, **flt)


def genres(p):
    kind = p['kind']
    for g in tmdb.genres(kind):
        _sorts_entry(g['name'], kind, genre=g['id'])
    end()


def years(p):
    kind = p['kind']
    folder('Year Ranges', action='ranges', kind=kind)
    folder('Decades', action='decades', kind=kind)
    folder('By Year', action='yearlist', kind=kind)
    folder('Custom Range...', action='custom_range', kind=kind)
    end()


def ranges(p):
    kind, y = p['kind'], date.today().year
    for label, y1, y2 in (('This Year', y, y), ('Last Year', y - 1, y - 1), ('Last 3 Years', y - 2, y), ('Last 5 Years', y - 4, y),
                          ('Last 10 Years', y - 9, y), ('2000 to Today', 2000, y), ('1990 to 1999', 1990, 1999), ('1980 to 1989', 1980, 1989),
                          ('Classics (before 1970)', 1900, 1969), ('Golden Age (1930-1959)', 1930, 1959)):
        _sorts_entry(label, kind, y1=y1, y2=y2)
    end()


def decades(p):
    kind = p['kind']
    for start in range(date.today().year // 10 * 10, 1899, -10):
        _sorts_entry("%ds" % start, kind, y1=start, y2=start + 9)
    end()


def yearlist(p):
    kind = p['kind']
    for y in range(date.today().year, 1899, -1):
        _sorts_entry(str(y), kind, y1=y, y2=y)
    end()


def custom_range(p):
    kind = p['kind']
    a = xbmcgui.Dialog().input('From year (e.g. 1995)', type=xbmcgui.INPUT_NUMERIC)
    b = xbmcgui.Dialog().input('To year (e.g. 2004)', type=xbmcgui.INPUT_NUMERIC)
    if not (a.isdigit() and b.isdigit()):
        return end()
    y1, y2 = sorted((int(a), int(b)))
    sorts({'kind': kind, 'y1': y1, 'y2': y2})


def themes(p):
    kind = p['kind']
    for label, kid in THEMES:
        _sorts_entry(label, kind, kw=kid)
    end()


def studios(p):
    for label, cid in STUDIOS:
        _sorts_entry(label, 'movie', company=cid)
    end()


def networks(p):
    for label, nid in NETWORKS:
        _sorts_entry(label, 'tv', network=nid)
    end()


# ------------------------------------------------------------------ title lists (posters)
def _year(r):
    return (r.get('release_date') or r.get('first_air_date') or '')[:4]


def title_item(kind, r):
    """One movie (playable) or show (folder) from a TMDB result."""
    tid = r['id']
    name = r.get('title') or r.get('name') or '?'
    year = _year(r)
    poster = tmdb.poster(r.get('poster_path'))
    li = xbmcgui.ListItem('%s (%s)' % (name, year) if year else name)
    li.setArt({'poster': poster, 'thumb': poster, 'icon': poster, 'fanart': tmdb.fanart(r.get('backdrop_path'))})
    tag = li.getVideoInfoTag()
    tag.setTitle(name)
    rating = r.get('vote_average')
    plot = r.get('overview') or ''
    tag.setPlot(('[B]%.1f[/B]  ' % rating if rating else '') + plot)
    tag.setMediaType('movie' if kind == 'movie' else 'tvshow')
    if year.isdigit():
        tag.setYear(int(year))
    if rating:
        tag.setRating(float(rating))
    menu = []
    if store.in_list(kind, tid):
        menu.append(('Remove from My List', 'RunPlugin(%s)' % url(action='unlist', kind=kind, id=tid)))
    else:
        menu.append(('Add to My List', 'RunPlugin(%s)' % url(action='tolist', kind=kind, id=tid, title=name, poster=poster)))
    menu.append(('More like this', 'Container.Update(%s)' % url(action='similar', kind=kind, id=tid, page=1)))
    if kind == 'movie':
        if store.is_watched(store.key('movie', tid)):
            tag.setPlaycount(1)
        li.setProperty('IsPlayable', 'true')
        menu.append(('Choose source...', 'PlayMedia(%s)' % url(action='play', kind='movie', id=tid, ask=1)))
        li.addContextMenuItems(menu)
        xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='movie', id=tid), li, False)
    else:
        li.addContextMenuItems(menu)
        xbmcplugin.addDirectoryItem(HANDLE, url(action='seasons', id=tid, name=name), li, True)


def person_item(r):
    img = tmdb.poster(r.get('profile_path'))
    li = xbmcgui.ListItem(r.get('name') or '?')
    li.setArt({'poster': img, 'thumb': img, 'icon': img})
    known = ', '.join((x.get('title') or x.get('name') or '') for x in (r.get('known_for') or [])[:3])
    li.getVideoInfoTag().setPlot('Known for: ' + known if known else '')
    xbmcplugin.addDirectoryItem(HANDLE, url(action='person', id=r['id'], name=r.get('name')), li, True)


def results(kind, data, nextargs):
    for r in data.get('results', []):
        k = kind
        if kind == 'multi':
            k = r.get('media_type')
            if k == 'person':
                person_item(r)
                continue
            if k not in ('movie', 'tv'):
                continue
        title_item(k, r)
    page = data.get('page', 1)
    if page < min(data.get('total_pages', 1), 50):
        folder('Next page (%d of %d)' % (page + 1, min(data.get('total_pages', 1), 50)), **dict(nextargs, page=page + 1))
    if not data.get('results'):
        common.notify('Nothing found here')
    end('tvshows' if kind == 'tv' else 'movies', view=True)


def list_(p):
    page = int(p.get('page', 1))
    results(p['kind'], tmdb.listing(p['kind'], p['which'], page), dict(action='list', kind=p['kind'], which=p['which']))


def browse(p):
    page = int(p.get('page', 1))
    f = {k: p[k] for k in FILTER_KEYS + ('sort',) if p.get(k)}
    results(p['kind'], tmdb.browse(p['kind'], f, page), dict(action='browse', kind=p['kind'], **f))


def similar(p):
    page = int(p.get('page', 1))
    results(p['kind'], tmdb.similar(p['kind'], int(p['id']), page), dict(action='similar', kind=p['kind'], id=p['id']))


# ------------------------------------------------------------------ search
def search_menu(_p):
    folder('Search Everything', action='search', scope='multi')
    folder('Search Movies', action='search', scope='movie')
    folder('Search TV Shows', action='search', scope='tv')
    folder('Search People (actors, directors)', action='search', scope='person')
    for h in store.search_history()[:12]:
        label = {'multi': '', 'movie': 'Movies: ', 'tv': 'TV: ', 'person': 'People: '}.get(h['scope'], '')
        folder('[COLOR grey]Recent:[/COLOR] %s%s' % (label, h['q']), action='search', scope=h['scope'], q=h['q'])
    if store.search_history():
        folder('[COLOR red]Clear search history[/COLOR]', action='clear_history')
    end(cache=False)


def search(p):
    scope = p.get('scope', 'multi')
    q = p.get('q') or xbmcgui.Dialog().input('Search')
    if not q:
        return end()
    page = int(p.get('page', 1))
    if page == 1:
        store.add_search(scope, q)
    data = tmdb.search(q, page, scope)
    if scope == 'person':
        for r in data.get('results', []):
            person_item(r)
        end('movies', view=True)
        return
    results('multi' if scope == 'multi' else scope, data, dict(action='search', scope=scope, q=q))


def person(p):
    data = tmdb.person_credits(int(p['id']))
    seen, rows = set(), []
    for r in sorted(data.get('cast', []) + data.get('crew', []), key=lambda r: r.get('popularity', 0), reverse=True):
        key = (r.get('media_type'), r.get('id'))
        if key in seen or r.get('media_type') not in ('movie', 'tv') or not r.get('poster_path'):
            continue
        seen.add(key)
        rows.append(r)
    for r in rows[:60]:
        title_item(r['media_type'], r)
    end('movies', view=True)


def clear_history(_p):
    store.clear_search()
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------------ TV drill-down
def seasons(p):
    tid = int(p['id'])
    s = tmdb.show(tid)
    for se in s.get('seasons', []):
        n = se['season_number']
        if n == 0 and not se.get('episode_count'):
            continue
        count = se.get('episode_count') or 0
        li = xbmcgui.ListItem('Season %d' % n if n else 'Specials')
        poster = tmdb.poster(se.get('poster_path') or s.get('poster_path'))
        li.setArt({'poster': poster, 'thumb': poster, 'fanart': tmdb.fanart(s.get('backdrop_path'))})
        tag = li.getVideoInfoTag()
        tag.setMediaType('season')
        tag.setSeason(n)
        tag.setTvShowTitle(s.get('name') or '')
        tag.setPlot('%d episodes\n\n%s' % (count, se.get('overview') or s.get('overview') or ''))
        xbmcplugin.addDirectoryItem(HANDLE, url(action='episodes', id=tid, season=n), li, True)
    end('seasons', view=True)


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
        if e.get('runtime'):
            tag.setDuration(int(e['runtime']) * 60)
        if store.is_watched(store.key('episode', tid, n, num)):
            tag.setPlaycount(1)
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems([('Choose source...', 'PlayMedia(%s)' % url(action='play', kind='episode', id=tid, season=n, episode=num, ask=1))])
        xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='episode', id=tid, season=n, episode=num), li, False)
    end('episodes')


# ------------------------------------------------------------------ continue / my list
def continue_(_p):
    for v in store.continue_items():
        sub = ''
        if v['kind'] == 'episode':
            sub = ' - S%02dE%02d%s' % (v['season'], v['episode'], ' ' + v['sub'] if v.get('sub') else '')
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
    end('movies', cache=False, view=True)


def mylist(_p):
    for x in store.mylist():
        poster = x.get('poster') or ''
        li = xbmcgui.ListItem(x['title'])
        li.setArt({'poster': poster, 'thumb': poster})
        li.addContextMenuItems([('Remove from My List', 'RunPlugin(%s)' % url(action='unlist', kind=x['kind'], id=x['id']))])
        if x['kind'] == 'movie':
            li.setProperty('IsPlayable', 'true')
            li.getVideoInfoTag().setMediaType('movie')
            xbmcplugin.addDirectoryItem(HANDLE, url(action='play', kind='movie', id=x['id']), li, False)
        else:
            li.getVideoInfoTag().setMediaType('tvshow')
            xbmcplugin.addDirectoryItem(HANDLE, url(action='seasons', id=x['id'], name=x['title']), li, True)
    end('movies', cache=False, view=True)


def tolist(p):
    store.add_to_list(p['kind'], int(p['id']), p.get('title', ''), p.get('poster', ''))
    common.notify('Added to My List')


def unlist(p):
    store.remove_from_list(p['kind'], int(p['id']))
    common.notify('Removed from My List')
    xbmc.executebuiltin('Container.Refresh')


def cw_remove(p):
    store.remove_progress(p['key'])
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------------ tools
def tools(_p):
    folder('Check my accounts', action='check_accounts')
    folder('Settings', action='settings')
    folder('Clear cached lists (fixes stale or odd results)', action='clear_cache')
    folder('Forget blocked releases', action='clear_blocked')
    end(cache=False)


def check_accounts(_p):
    lines = []
    try:
        u = rd.account()
        lines.append('Real-Debrid: %s (%s) until %s' % (u.get('username'), u.get('type'), (u.get('expiration') or '')[:10]))
    except Exception as e:
        lines.append('Real-Debrid: %s' % e)
    try:
        tmdb.get('configuration')
        lines.append('TMDB: reachable, key works')
    except Exception as e:
        lines.append('TMDB: %s' % e)
    try:
        from cocoscrapers import sources as coco
        names = [n for n, _ in coco()]
        lines.append('CocoScrapers: %d providers enabled (%s)' % (len(names), ', '.join(names[:8]) + ('...' if len(names) > 8 else '')))
    except Exception as e:
        lines.append('CocoScrapers: not available (%s)' % e)
    xbmcgui.Dialog().ok(common.NAME, '\n'.join(lines))


def clear_cache(_p):
    common.save('cache.json', {})
    common.notify('Cache cleared')


def clear_blocked(_p):
    common.save('blocked.json', {})
    common.notify('Blocked list cleared')


def settings(_p):
    common.ADDON.openSettings()


ROUTES = {
    'root': root, 'menu': menu, 'sorts': sorts, 'genres': genres, 'years': years, 'ranges': ranges, 'decades': decades,
    'yearlist': yearlist, 'custom_range': custom_range, 'themes': themes, 'studios': studios, 'networks': networks,
    'list': list_, 'browse': browse, 'similar': similar, 'search_menu': search_menu, 'search': search, 'person': person,
    'clear_history': clear_history, 'seasons': seasons, 'episodes': episodes, 'continue': continue_, 'mylist': mylist,
    'tolist': tolist, 'unlist': unlist, 'cw_remove': cw_remove, 'tools': tools, 'check_accounts': check_accounts,
    'clear_cache': clear_cache, 'clear_blocked': clear_blocked, 'settings': settings,
}


def dispatch(argv):
    from . import player
    params = dict(parse_qsl(argv[2][1:])) if len(argv) > 2 else {}
    action = params.get('action', 'root')
    if action == 'play':
        return player.play(HANDLE, params['kind'], int(params['id']),
                           int(params['season']) if params.get('season') not in (None, '', 'None') else None,
                           int(params['episode']) if params.get('episode') not in (None, '', 'None') else None,
                           ask=params.get('ask') == '1')
    try:
        ROUTES.get(action, root)(params)
    except tmdb.TMDBError as e:
        xbmcgui.Dialog().ok(common.NAME, str(e))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
