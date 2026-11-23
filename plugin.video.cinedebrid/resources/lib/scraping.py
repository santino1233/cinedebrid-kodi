# -*- coding: utf-8 -*-
"""Run every provider you enabled in CocoScrapers in parallel and return merged, de-duplicated releases."""
import threading
import time

import xbmc
import xbmcgui

from . import common, rank


def _providers():
    try:
        from cocoscrapers import sources as coco_sources
    except Exception as e:  # CocoScrapers missing or broken
        common.log('CocoScrapers import failed: %s' % e, xbmc.LOGERROR)
        raise RuntimeError('CocoScrapers is not available. Install/enable script.module.cocoscrapers.')
    found = coco_sources()
    if not found:
        raise RuntimeError('No scrapers are enabled in CocoScrapers. Open CocoScrapers settings and enable some providers.')
    return found


def _run(name, cls, data, packs, out, done):
    try:
        s = cls()
        rows = list(s.sources(data, []) or [])
        if packs and data.get('tvshowtitle') and getattr(s, 'pack_capable', False) and hasattr(s, 'sources_packs'):
            try:
                rows += list(s.sources_packs(data, [], search_series=False, total_seasons=None) or [])
            except Exception as e:
                common.log('%s packs failed: %s' % (name, e))
        for r in rows:
            r.setdefault('provider', name)
        out.append((name, rows, None))
    except Exception as e:
        out.append((name, [], str(e)[:80]))
        common.log('%s failed: %s' % (name, e), xbmc.LOGWARNING)
    finally:
        done.append(name)


def search(data, show_progress=True):
    """data: the dict CocoScrapers providers expect (title, year, imdb, aliases, and for TV tvshowtitle/season/episode)."""
    providers = _providers()
    limit = common.setting_int('scrape_timeout', 20)
    packs = common.setting_bool('packs', True) and bool(data.get('tvshowtitle'))
    out, done, threads = [], [], []
    for name, cls in providers:
        t = threading.Thread(target=_run, args=(name, cls, data, packs, out, done), daemon=True)
        t.start()
        threads.append(t)
    dlg = None
    if show_progress:
        dlg = xbmcgui.DialogProgress()
        dlg.create(common.NAME, 'Searching %d sites…' % len(providers))
    start = time.time()
    cancelled = False
    try:
        while len(done) < len(threads):
            elapsed = time.time() - start
            have = sum(len(r) for _, r, _ in list(out))
            if elapsed >= limit or (elapsed >= max(8, limit * 0.5) and have >= 25 and len(done) >= len(threads) * 0.6):
                break
            if dlg:
                if dlg.iscanceled():
                    cancelled = True
                    break
                dlg.update(int(min(95, elapsed / limit * 100)), '%d of %d sites answered · %d releases found' % (len(done), len(threads), have))
            xbmc.sleep(200)
    finally:
        if dlg:
            dlg.close()
    rows = [r for _, rs, _ in list(out) for r in rs]
    merged = rank.merge(rows)
    common.log('scrape: %d providers, %d raw, %d unique, %.1fs%s' % (len(providers), len(rows), len(merged), time.time() - start, ' (cancelled)' if cancelled else ''))
    return merged
