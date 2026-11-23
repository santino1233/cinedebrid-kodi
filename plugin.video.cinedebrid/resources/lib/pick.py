# -*- coding: utf-8 -*-
"""Choose which file inside a Real-Debrid torrent to play (kodi-independent, unit-tested)."""
import re

VIDEO = re.compile(r'\.(mkv|mp4|avi|m4v|mov|wmv|ts|m2ts|webm)$', re.I)
JUNK = re.compile(r'(^|[/\\._ -])(sample|trailer|extras?|featurettes?|behind.the.scenes|bonus|deleted.scenes?)([/\\._ -]|$)', re.I)


def is_episode(path, season, episode):
    name = path.replace('\\', '/').split('/')[-1]
    s, e = int(season), int(episode)
    pats = [
        r'[Ss]0*%d[ ._-]*[Ee]0*%d(?!\d)' % (s, e),
        r'(?<!\d)0*%dx0*%d(?!\d)' % (s, e),
        r'[Ss]eason[ ._-]*0*%d[ ._-]*[Ee]pisode[ ._-]*0*%d(?!\d)' % (s, e),
    ]
    return any(re.search(p, name) for p in pats)


def pick_file(files, season=None, episode=None):
    """files: Real-Debrid file dicts {id, path, bytes}. Raises LookupError when nothing fits."""
    vids = [f for f in files if VIDEO.search(f.get('path', ''))]
    clean = [f for f in vids if not JUNK.search(f.get('path', ''))] or vids
    if not clean:
        raise LookupError('no video file in this torrent')
    if season is not None and episode is not None:
        hits = [f for f in clean if is_episode(f['path'], season, episode)]
        if not hits:
            raise LookupError('episode not in this torrent')
        return max(hits, key=lambda f: f.get('bytes', 0))
    return max(clean, key=lambda f: f.get('bytes', 0))
