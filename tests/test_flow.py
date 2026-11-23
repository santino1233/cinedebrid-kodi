# -*- coding: utf-8 -*-
"""End-to-end flow with a fake Kodi, fake TMDB/RD/CocoScrapers: menus, auto-play, fallbacks, Continue Watching."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kodistubs  # noqa: E402

kodistubs.install()
sys.modules.setdefault('requests', __import__('types').ModuleType('requests'))
sys.modules['requests'].RequestException = Exception

from resources.lib import common, rd, router, scraping, store, tmdb  # noqa: E402
from resources.lib import player  # noqa: E402

E = kodistubs.EVENTS
H = lambda n: '%040x' % n

MOVIE = {'id': 8292, 'title': 'Four Brothers', 'original_title': 'Four Brothers', 'release_date': '2005-08-12', 'poster_path': '/p.jpg',
         'backdrop_path': '/b.jpg', 'overview': 'x', 'external_ids': {'imdb_id': 'tt0430105'}}
ROWS = [
    {'hash': H(1), 'name': 'Four.Brothers.2005.1080p.BluRay.Remux.DTS-HD', 'name_info': 'remux', 'quality': '1080p', 'seeders': 22, 'size': 17.0, 'provider': 'a'},
    {'hash': H(2), 'name': 'Four.Brothers.2005.1080p.BluRay.x265-RARBG', 'name_info': 'x265', 'quality': '1080p', 'seeders': 3, 'size': 1.7, 'provider': 'b'},
    {'hash': H(3), 'name': 'Four.Brothers.2005.720p', 'name_info': '720p', 'quality': '720p', 'seeders': 30, 'size': 1.0, 'provider': 'c'},
]


class Flow(unittest.TestCase):
    def setUp(self):
        del E[:]
        kodistubs.SETTINGS.clear()
        kodistubs.SETTINGS.update({'tmdb_key': 'k', 'rd_token': 't', 'autoplay': 'true', 'max_res': '1080', 'max_size': '20', 'allow_uncached': 'true'})
        for f in os.listdir(kodistubs.PROFILE):
            os.remove(os.path.join(kodistubs.PROFILE, f))
        tmdb.movie = lambda tid: MOVIE
        scraping.search = lambda data, show_progress=True: [dict(r) for r in ROWS]
        self.start_calls = []
        self.cached_hashes = set()
        self.blocked_hashes = set()

        def start(h, season=None, episode=None):
            self.start_calls.append(h)
            if h in self.blocked_hashes:
                raise rd.RDError('blocked', blocked=True)
            return 'T' + h[-2:], False

        def wait_ready(tid, season=None, episode=None, seconds=8, progress=None):
            h = [x for x in self.start_calls][-1]
            return {'status': 'downloaded' if h in self.cached_hashes else 'downloading', 'progress': 0, 'files': [], 'links': []}

        rd.start, rd.wait_ready = start, wait_ready
        rd.stream_url = lambda info, s=None, e=None: ('https://dl.real-debrid.com/d/' + self.start_calls[-1], 'f.mkv')
        rd.discard = lambda tid: None

    def resolved(self):
        return [e for e in E if e[0] == 'resolved']

    def test_autoplay_skips_uncached_and_blocked_and_plays_next(self):
        self.blocked_hashes = {H(2)}
        self.cached_hashes = {H(3)}
        player.play(1, 'movie', 8292)
        # best-ranked first (RARBG x265 is blocked), then the REMUX/720p; the cached one must win
        res = self.resolved()
        self.assertEqual(len(res), 1)
        self.assertTrue(res[0][1])
        self.assertTrue(res[0][2].endswith(H(3)))

    def test_autoplay_prefers_best_cached(self):
        self.cached_hashes = {H(2), H(3)}
        player.play(1, 'movie', 8292)
        self.assertTrue(self.resolved()[0][2].endswith(H(2)))  # 1080p RARBG beats 720p

    def test_nothing_cached_falls_back_to_source_list_then_cancel(self):
        kodistubs.xbmcgui = sys.modules['xbmcgui']
        sys.modules['xbmcgui'].Dialog.answers = [-1]
        player.play(1, 'movie', 8292)
        self.assertTrue(any(e[0] == 'select' for e in E))
        self.assertEqual(self.resolved(), [('resolved', False, '')])

    def test_ask_mode_shows_list_and_plays_pick(self):
        self.cached_hashes = {H(3)}
        sys.modules['xbmcgui'].Dialog.answers = [2]  # third entry in ranked order
        player.play(1, 'movie', 8292, ask=True)
        sel = [e for e in E if e[0] == 'select'][0]
        self.assertEqual(sel[2], 3)
        self.assertTrue(self.resolved()[0][1])

    def test_progress_saved_and_finished_marks_watched(self):
        self.cached_hashes = {H(2)}
        player.play(1, 'movie', 8292)
        # fake player reports 3000/3300 s = 90.9%: saved for Continue Watching, not yet finished
        cw = store.continue_items()
        self.assertEqual(len(cw), 1)  # 90.9% is not "finished": it stays in Continue Watching
        self.assertEqual(cw[0]['pos'], 3000.0)
        self.assertFalse(store.is_watched(store.key('movie', 8292)))

    def test_finished_episode_queues_up_next(self):
        tmdb.season = lambda tid, n: {'episodes': [{'episode_number': 1, 'name': 'One'}, {'episode_number': 2, 'name': 'Two'}]}
        info = {'show': 'Show', 'title': 'Show S01E01', 'poster': 'p', 'fanart': 'f', 'episode_name': 'One'}
        store.save_progress('episode', 5, 1, 1, info, 2900, 3000)
        store.finished('episode', 5, 1, 1, info)
        cw = store.continue_items()
        self.assertEqual(len(cw), 1)
        self.assertTrue(cw[0]['next'])
        self.assertEqual((cw[0]['season'], cw[0]['episode']), (1, 2))
        self.assertTrue(store.is_watched(store.key('episode', 5, 1, 1)))

    def test_menus_build(self):
        router.root({})
        self.assertIn('Movies', [e[1] for e in E if e[0] == 'item'])
        del E[:]
        tmdb.listing = lambda kind, which, page=1, **kw: {'page': 1, 'total_pages': 3, 'results': [MOVIE]}
        router.list_({'kind': 'movie', 'which': 'popular', 'page': '1'})
        items = [e for e in E if e[0] == 'item']
        self.assertEqual(items[0][2], False)               # a movie is playable (not a folder)
        self.assertIn('action=play', items[0][3])
        self.assertTrue(items[-1][1].startswith('Next page'))

    def test_my_list_roundtrip(self):
        store.add_to_list('movie', 8292, 'Four Brothers', 'p')
        self.assertTrue(store.in_list('movie', 8292))
        store.remove_from_list('movie', 8292)
        self.assertFalse(store.in_list('movie', 8292))


if __name__ == '__main__':
    unittest.main()
