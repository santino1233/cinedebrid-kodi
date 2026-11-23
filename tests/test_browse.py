# -*- coding: utf-8 -*-
"""Navigation and TMDB-query tests with a fake Kodi: organisation, filters, poster view, network resilience."""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kodistubs  # noqa: E402

kodistubs.install()
req = sys.modules.setdefault('requests', __import__('types').ModuleType('requests'))
req.RequestException = type('RequestException', (Exception,), {})

from resources.lib import common, router, store, tmdb  # noqa: E402

E = kodistubs.EVENTS


def labels():
    return [e[1] for e in E if e[0] == 'item']


def items():
    return [e for e in E if e[0] == 'item']


class Navigation(unittest.TestCase):
    def setUp(self):
        del E[:]
        kodistubs.SETTINGS.clear()
        kodistubs.SETTINGS.update({'tmdb_key': 'k', 'view_mode': 'poster'})
        for f in os.listdir(kodistubs.PROFILE):
            os.remove(os.path.join(kodistubs.PROFILE, f))
        self.queries = []
        tmdb.get = lambda path, **kw: (self.queries.append((path, kw)) or {'page': 1, 'total_pages': 1, 'results': [
            {'id': 1, 'title': 'A', 'name': 'A', 'release_date': '2001-01-01', 'poster_path': '/a.jpg', 'vote_average': 7.5, 'overview': 'x'}]})
        tmdb.genres = lambda kind: [{'id': 28, 'name': 'Action'}, {'id': 35, 'name': 'Comedy'}]

    def test_root_is_short_and_organised(self):
        router.root({})
        self.assertEqual(labels(), ['Movies', 'TV Shows', 'Search', 'My List', 'Tools & Settings'])

    def test_movie_menu_has_the_categories(self):
        router.menu({'kind': 'movie'})
        got = labels()
        for want in ('Genres', 'Years & Decades', 'Themes & Collections', 'Studios', 'Critically Acclaimed', 'Hidden Gems', 'Box Office Hits', 'Upcoming'):
            self.assertIn(want, got)

    def test_tv_menu_has_networks_and_tv_only_categories(self):
        router.menu({'kind': 'tv'})
        got = labels()
        for want in ('Networks & Streaming', 'Mini-Series', 'Anime', 'On The Air', 'Airing Today'):
            self.assertIn(want, got)
        self.assertNotIn('Box Office Hits', got)

    def test_year_menus(self):
        router.years({'kind': 'movie'})
        self.assertEqual(labels(), ['Year Ranges', 'Decades', 'By Year', 'Custom Range...'])
        del E[:]
        router.ranges({'kind': 'movie'})
        self.assertIn('Last 5 Years', labels())
        self.assertIn('Classics (before 1970)', labels())
        del E[:]
        router.decades({'kind': 'tv'})
        self.assertEqual(labels()[0], '%ds' % (date.today().year // 10 * 10))
        self.assertEqual(labels()[-1], '1900s')
        del E[:]
        router.yearlist({'kind': 'movie'})
        self.assertEqual(labels()[0], str(date.today().year))

    def test_custom_range_sorts_years(self):
        kodistubs.sys = sys
        sys.modules['xbmcgui'].Dialog.inputs = ['2004', '1995']
        router.custom_range({'kind': 'movie'})
        urls = [e[3] for e in items()]
        self.assertTrue(all('y1=1995' in u and 'y2=2004' in u for u in urls), urls)
        self.assertEqual(labels(), ['Popular', 'Top Rated', 'Newest First', 'Hidden Gems'])

    def test_sorts_keep_the_filter(self):
        router.sorts({'kind': 'movie', 'genre': '28', 'y1': '1990', 'y2': '1999'})
        for e in items():
            self.assertIn('genre=28', e[3])
            self.assertIn('y1=1990', e[3])
            self.assertIn('action=browse', e[3])

    def test_browse_builds_tmdb_query(self):
        router.browse({'kind': 'movie', 'genre': '28', 'y1': '1990', 'y2': '1999', 'sort': 'top', 'page': '1'})
        path, kw = self.queries[-1]
        self.assertEqual(path, 'discover/movie')
        self.assertEqual(kw['with_genres'], '28')
        self.assertEqual(kw['primary_release_date.gte'], '1990-01-01')
        self.assertEqual(kw['primary_release_date.lte'], '1999-12-31')
        self.assertEqual(kw['sort_by'], 'vote_average.desc')
        self.assertEqual(kw['vote_count.gte'], 500)

    def test_tv_browse_uses_tv_fields(self):
        router.browse({'kind': 'tv', 'network': '213', 'sort': 'newest', 'days': '90', 'page': '1'})
        path, kw = self.queries[-1]
        self.assertEqual(path, 'discover/tv')
        self.assertEqual(kw['with_networks'], '213')
        self.assertEqual(kw['sort_by'], 'first_air_date.desc')
        self.assertIn('first_air_date.gte', kw)
        self.assertNotIn('primary_release_date.gte', kw)

    def test_results_are_posters_and_set_poster_view(self):
        router.browse({'kind': 'movie', 'sort': 'popular', 'page': '1'})
        self.assertIn(('builtin', 'Container.SetViewMode(51)'), E)
        li = items()[0]
        self.assertFalse(li[2])  # a movie is playable, not a folder

    def test_view_mode_can_be_left_to_the_skin(self):
        kodistubs.SETTINGS['view_mode'] = 'skin'
        router.browse({'kind': 'movie', 'sort': 'popular', 'page': '1'})
        self.assertFalse([e for e in E if e[0] == 'builtin'])

    def test_search_history_and_person(self):
        tmdb.search = lambda q, page=1, scope='multi': {'page': 1, 'total_pages': 1, 'results': [
            {'id': 9, 'name': 'Tom Hanks', 'media_type': 'person', 'profile_path': '/p.jpg', 'known_for': [{'title': 'Big'}]},
            {'id': 3, 'title': 'Big', 'media_type': 'movie', 'release_date': '1988-06-03', 'poster_path': '/b.jpg'}]}
        router.search({'scope': 'multi', 'q': 'hanks'})
        self.assertEqual(labels(), ['Tom Hanks', 'Big (1988)'])
        self.assertIn('action=person', items()[0][3])
        self.assertEqual(store.search_history()[0]['q'], 'hanks')
        del E[:]
        router.search_menu({})
        self.assertTrue(any('Recent:' in l for l in labels()))


class Network(unittest.TestCase):
    def setUp(self):
        kodistubs.SETTINGS.clear()
        kodistubs.SETTINGS['tmdb_key'] = 'k'
        for f in os.listdir(kodistubs.PROFILE):
            os.remove(os.path.join(kodistubs.PROFILE, f))
        import importlib
        importlib.reload(tmdb)
        tmdb.time.sleep = lambda s: None
        self.calls = []

    def test_second_domain_is_tried(self):
        class R:
            status_code = 200
            def json(self): return {'ok': True}

        def fake_get(u, **k):
            self.calls.append(u)
            if 'api.themoviedb.org' in u:
                raise req.RequestException('dns')
            return R()
        req.get = fake_get
        self.assertEqual(tmdb.get('movie/1'), {'ok': True})
        self.assertIn('api.tmdb.org', self.calls[-1])

    def test_stale_cache_is_used_when_offline(self):
        class R:
            status_code = 200
            def json(self): return {'v': 1}
        req.get = lambda u, **k: R()
        tmdb.get('movie/2')
        store_ = common.load('cache.json', {})
        for v in store_.values():
            v['at'] -= 7200  # expired (ttl 1 h) but inside the 7-day stale window
        common.save('cache.json', store_)

        def offline(u, **k):
            raise req.RequestException('no network')
        req.get = offline
        self.assertEqual(tmdb.get('movie/2'), {'v': 1})

    def test_clear_error_when_unreachable(self):
        def offline(u, **k):
            raise req.RequestException('no network')
        req.get = offline
        with self.assertRaises(tmdb.TMDBError) as cm:
            tmdb.get('movie/3')
        self.assertIn('DNS', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
