# -*- coding: utf-8 -*-
"""Kodi-independent ranking and merging of scraper results (unit-tested in tests/test_rank.py)."""
import re

RES_ORDER = {'4K': 2160, '2160P': 2160, '1080P': 1080, '720P': 720, 'SD': 480, 'CAM': 0, 'SCR': 0, 'TELE': 0}
RES_BASE = {2160: 3000, 1080: 2000, 720: 1000, 480: 0, 0: -3000}
TRUSTED = (('RARBG', re.compile(r'rarbg|\brbg\b', re.I)), ('YIFY', re.compile(r'yify|\byts\b', re.I)))
SOURCE = (('REMUX', r'remux'), ('BluRay', r'blu-?ray|bdrip|brrip'), ('WEB-DL', r'web-?dl|webrip|\bweb\b'), ('HDTV', r'hdtv'), ('DVD', r'dvd'))
AUDIO_HARD = re.compile(r'atmos|truehd|dts|dd\+|ddp|eac3|e-ac-3', re.I)  # Kodi plays these, but they pass through to a receiver


def res_of(item):
    return RES_ORDER.get(str(item.get('quality', '')).upper(), 480)


def describe(item):
    """Parsed facts about a release, used for labels and ranking."""
    name = ' '.join([str(item.get('name') or ''), str(item.get('name_info') or '')])
    src = next((label for label, pat in SOURCE if re.search(pat, name, re.I)), '')
    trusted = [label for label, pat in TRUSTED if pat.search(name) or pat.search(str(item.get('provider', '')))]
    return {
        'res': res_of(item),
        'source': src,
        'remux': bool(re.search(r'remux', name, re.I)),
        'hevc': bool(re.search(r'x265|h\.?265|hevc', name, re.I)),
        'hdr': bool(re.search(r'\bhdr10?\+?\b|\bdv\b|dolby.?vision', name, re.I)),
        'trusted': trusted,
        'cam': res_of(item) == 0,
    }


def merge(rows):
    """One entry per infohash: keep the best seeders/size, remember every provider that found it."""
    out = {}
    for r in rows:
        h = str(r.get('hash') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{40}', h):
            continue
        r = dict(r, hash=h)
        r.setdefault('providers', [])
        prov = r.get('provider')
        if h not in out:
            out[h] = dict(r, providers=[prov] if prov else [])
        else:
            m = out[h]
            if prov and prov not in m['providers']:
                m['providers'].append(prov)
            m['seeders'] = max(int(m.get('seeders') or 0), int(r.get('seeders') or 0))
            m['size'] = m.get('size') or r.get('size')
    return list(out.values())


def score(item, prefer_streamable=True):
    d = describe(item)
    s = RES_BASE.get(d['res'], 0)
    s += 400 if d['trusted'] else 0
    s += {'BluRay': 120, 'REMUX': 100, 'WEB-DL': 90, 'HDTV': 20, 'DVD': -80}.get(d['source'], 0)
    s += min(int(item.get('seeders') or 0), 60) * 4
    if d['remux'] and prefer_streamable:
        s -= 700
    size = float(item.get('size') or 0)  # GB, as the scrapers report it
    if prefer_streamable and size > 40:
        s -= 300
    return s


def usable(items, max_res=1080, max_size_gb=0, allow_cam=False):
    out = []
    for i in items:
        d = describe(i)
        if d['cam'] and not allow_cam:
            continue
        size = float(i.get('size') or 0)
        if max_size_gb and size and size > max_size_gb:
            continue
        out.append(i)
    return out


def ordered(items, prefer_streamable=True):
    return sorted(items, key=lambda i: score(i, prefer_streamable), reverse=True)


def autoplay_candidates(items, max_res, max_size_gb, prefer_streamable=True, limit=6):
    """The sources worth trying automatically: not above the chosen quality, not oversized, best first."""
    fit = [i for i in usable(items, max_res, max_size_gb) if describe(i)['res'] <= max_res]
    return ordered(fit, prefer_streamable)[:limit]


def label(item):
    d = describe(item)
    size = float(item.get('size') or 0)
    res = {2160: '4K', 1080: '1080p', 720: '720p', 480: 'SD', 0: 'CAM'}.get(d['res'], '?')
    parts = [res]
    if d['source']:
        parts.append(d['source'])
    if d['hevc']:
        parts.append('HEVC')
    if d['hdr']:
        parts.append('HDR')
    if size:
        parts.append('%.1f GB' % size)
    parts.append('%s seeds' % int(item.get('seeders') or 0))
    if d['trusted']:
        parts.append('/'.join(d['trusted']))
    return ' | '.join(parts)
