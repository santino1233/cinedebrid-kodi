# -*- coding: utf-8 -*-
"""Find sources, pick/ask, resolve through Real-Debrid and hand the URL to Kodi's own player.

Kodi decodes MKV, HEVC, 10-bit, HDR and DTS/TrueHD natively, so unlike a browser nothing has to be converted."""
import sys
import time

import xbmc
import xbmcgui
import xbmcplugin

from . import common, rank, rd, scraping, store, tmdb


class Cancelled(Exception):
    pass


def _meta(kind, tmdb_id, season, episode):
    """Everything CocoScrapers providers want, plus display info."""
    if kind == 'movie':
        m = tmdb.movie(tmdb_id)
        year = (m.get('release_date') or '')[:4]
        data = {'title': m.get('title') or '', 'year': year, 'imdb': (m.get('external_ids') or {}).get('imdb_id') or m.get('imdb_id') or '',
                'tmdb': str(tmdb_id), 'aliases': [m.get('original_title')] if m.get('original_title') != m.get('title') else [],
                'premiered': m.get('release_date') or ''}
        info = {'title': data['title'], 'poster': tmdb.poster(m.get('poster_path')), 'fanart': tmdb.fanart(m.get('backdrop_path')),
                'plot': m.get('overview') or '', 'year': year}
        return data, info
    s = tmdb.show(tmdb_id)
    ep = {}
    for e in tmdb.season(tmdb_id, season).get('episodes', []):
        if e.get('episode_number') == episode:
            ep = e
    year = (s.get('first_air_date') or '')[:4]
    titles = [x.get('title') for x in (s.get('alternative_titles') or {}).get('results', []) if x.get('title')][:6]
    data = {'tvshowtitle': s.get('name') or '', 'title': ep.get('name') or '', 'year': year, 'imdb': (s.get('external_ids') or {}).get('imdb_id') or '',
            'tmdb': str(tmdb_id), 'tvdb': str((s.get('external_ids') or {}).get('tvdb_id') or ''), 'season': str(season), 'episode': str(episode),
            'aliases': titles, 'premiered': ep.get('air_date') or '', 'status': s.get('status') or ''}
    info = {'title': '%s S%02dE%02d %s' % (data['tvshowtitle'], season, episode, data['title']), 'poster': tmdb.poster(s.get('poster_path')),
            'fanart': tmdb.fanart(s.get('backdrop_path')), 'plot': ep.get('overview') or s.get('overview') or '', 'year': year,
            'episode_name': data['title'], 'show': data['tvshowtitle']}
    return data, info


def _resolve(item, season, episode, wait, interactive):
    """Return a playable URL or None. interactive=True keeps going (with a progress dialog) while Real-Debrid downloads."""
    tid, created = rd.start(item['hash'], season, episode)
    dlg = None
    try:
        info = rd.wait_ready(tid, season, episode, seconds=wait)
        if info.get('status') != 'downloaded':
            if not interactive:
                if created:
                    rd.discard(tid)
                return None
            dlg = xbmcgui.DialogProgress()
            dlg.create(common.NAME, 'Sending to Real-Debrid…')

            def tick(i):
                pct = int(i.get('progress') or 0)
                speed = float(i.get('speed') or 0) / 1e6
                dlg.update(pct, 'Downloading on Real-Debrid: %d%%  ·  %.1f MB/s  ·  %s seeders\n%s' % (pct, speed, i.get('seeders') or 0, item.get('name', '')[:70]))
                return dlg.iscanceled()

            info = rd.wait_ready(tid, season, episode, seconds=3 * 3600, progress=tick)
            if info.get('status') != 'downloaded':
                if created:
                    rd.discard(tid)
                raise Cancelled()
        url, filename = rd.stream_url(info, season, episode)
        return url
    finally:
        if dlg:
            dlg.close()


def _try_auto(cands, season, episode):
    dlg = xbmcgui.DialogProgress()
    dlg.create(common.NAME, 'Checking Real-Debrid…')
    try:
        for n, item in enumerate(cands):
            if dlg.iscanceled():
                raise Cancelled()
            dlg.update(int(n / max(1, len(cands)) * 100), 'Trying source %d of %d\n%s' % (n + 1, len(cands), rank.label(item)))
            try:
                url = _resolve(item, season, episode, wait=6, interactive=False)
            except rd.RDError as e:
                if e.fatal:
                    raise
                common.log('skip %s: %s' % (item.get('name'), e))
                continue
            except LookupError:
                continue
            if url:
                return url, item
    finally:
        dlg.close()
    return None, None


def _choose(items, season, episode):
    """Manual source list. Returns (url, item) or (None, None)."""
    ordered = rank.ordered(items, common.setting_bool('prefer_streamable', True))[:60]
    labels = []
    for i in ordered:
        d = rank.describe(i)
        mark = '[COLOR gold]★[/COLOR] ' if d['trusted'] else ''
        labels.append('%s%s  [COLOR grey]%s[/COLOR]' % (mark, rank.label(i), (i.get('name') or '')[:60]))
    while True:
        pick = xbmcgui.Dialog().select('Sources (%d) — best first' % len(ordered), labels)
        if pick < 0:
            return None, None
        item = ordered[pick]
        try:
            url = _resolve(item, season, episode, wait=8, interactive=common.setting_bool('allow_uncached', True))
        except Cancelled:
            continue
        except LookupError:
            xbmcgui.Dialog().ok(common.NAME, 'That release does not contain this episode. Pick another.')
            continue
        except rd.RDError as e:
            if e.fatal:
                raise
            xbmcgui.Dialog().ok(common.NAME, str(e))
            continue
        if url:
            return url, item
        xbmcgui.Dialog().ok(common.NAME, 'Not cached on Real-Debrid. Enable “Offer sources that are not cached” in settings to download it first.')


def play(handle, kind, tmdb_id, season=None, episode=None, ask=False):
    failed = lambda: xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
    try:
        data, info = _meta(kind, tmdb_id, season, episode)
        rows = scraping.search(data)
        rows = [r for r in rows if not rd.is_blocked(r['hash'])]
        if not rows:
            xbmcgui.Dialog().ok(common.NAME, 'No sources found for this title. Check that providers are enabled in CocoScrapers.')
            return failed()
        url = item = None
        if common.setting_bool('autoplay', True) and not ask:
            cands = rank.autoplay_candidates(rows, common.setting_int('max_res', 1080), common.setting_int('max_size', 20),
                                             common.setting_bool('prefer_streamable', True))
            url, item = _try_auto(cands, season, episode)
            if not url:
                xbmcgui.Dialog().notification(common.NAME, 'Nothing cached right now. Pick a source.', common.ICON, 4000)
        if not url:
            url, item = _choose(rows, season, episode)
        if not url:
            return failed()
    except Cancelled:
        return failed()
    except (rd.RDError, tmdb.TMDBError, RuntimeError) as e:
        xbmcgui.Dialog().ok(common.NAME, str(e))
        return failed()

    key = store.key(kind, tmdb_id, season, episode)
    saved = store.get_progress(key)
    resume = 0
    if saved and saved.get('pos', 0) > 30 and saved['pos'] < 0.93 * max(1, saved.get('total', 1)):
        m, s = divmod(int(saved['pos']), 60)
        h, m = divmod(m, 60)
        stamp = '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)
        choice = xbmcgui.Dialog().contextmenu(['Resume from %s' % stamp, 'Play from beginning'])
        if choice == 0:
            resume = int(saved['pos'])
    li = xbmcgui.ListItem(path=url)
    li.setArt({'poster': info['poster'], 'thumb': info['poster'], 'fanart': info['fanart']})
    tag = li.getVideoInfoTag()
    tag.setTitle(info['title'])
    tag.setPlot(info['plot'])
    tag.setMediaType('movie' if kind == 'movie' else 'episode')
    if resume:
        li.setProperty('StartOffset', str(resume))
    xbmcplugin.setResolvedUrl(handle, True, li)
    _track(url, kind, tmdb_id, season, episode, info)


def _track(url, kind, tmdb_id, season, episode, info):
    """Keep this process alive while Kodi plays, saving the position for Continue Watching."""
    mon, player = xbmc.Monitor(), xbmc.Player()
    for _ in range(80):
        if player.isPlaying() or mon.abortRequested():
            break
        mon.waitForAbort(0.5)
    pos = total = 0
    while player.isPlaying() and not mon.abortRequested():
        try:
            pos, total = player.getTime(), player.getTotalTime()
            if total > 0 and pos > 5:
                store.save_progress(kind, tmdb_id, season, episode, info, pos, total)
        except RuntimeError:
            break
        mon.waitForAbort(5)
    if total > 0 and pos / total >= 0.93:
        store.finished(kind, tmdb_id, season, episode, info)
