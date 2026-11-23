# -*- coding: utf-8 -*-
"""Pure-logic tests (no Kodi needed): ranking, merging and file picking."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plugin.video.cinedebrid', 'resources', 'lib'))
import rank  # noqa: E402
from pick import pick_file  # noqa: E402

H = lambda n: ('%040x' % n)


def rel(n, name, quality='1080p', seeders=10, size=2.0, provider='x'):
    return {'hash': H(n), 'name': name, 'name_info': name.lower(), 'quality': quality, 'seeders': seeders, 'size': size, 'provider': provider}


class Ranking(unittest.TestCase):
    def test_resolution_beats_seeders(self):
        a = rel(1, 'Movie.2005.2160p.WEB-DL', '4K', 1)
        b = rel(2, 'Movie.2005.720p.BluRay', '720p', 500)
        self.assertEqual(rank.ordered([b, a])[0]['hash'], a['hash'])

    def test_trusted_group_gets_a_boost(self):
        a = rel(1, 'Movie.2005.1080p.BluRay.x265-RARBG', seeders=3)
        b = rel(2, 'Movie.2005.1080p.BluRay.x264-NOGRP', seeders=20)
        self.assertEqual(rank.ordered([b, a])[0]['hash'], a['hash'])
        self.assertEqual(rank.describe(a)['trusted'], ['RARBG'])

    def test_remux_is_a_fallback_when_streamable_preferred(self):
        remux = rel(1, 'Movie.2005.1080p.BluRay.REMUX.AVC.DTS-HD', size=30, seeders=50)
        encode = rel(2, 'Movie.2005.1080p.BluRay.x264', size=8, seeders=10)
        self.assertEqual(rank.ordered([remux, encode], True)[0]['hash'], encode['hash'])
        self.assertEqual(rank.ordered([remux, encode], False)[0]['hash'], remux['hash'])

    def test_cam_dropped_and_size_cap(self):
        rows = [rel(1, 'Movie.CAM', 'CAM'), rel(2, 'Movie.1080p', size=50), rel(3, 'Movie.1080p.ok', size=5)]
        got = rank.autoplay_candidates(rows, 1080, 20)
        self.assertEqual([r['hash'] for r in got], [H(3)])

    def test_max_resolution_respected(self):
        rows = [rel(1, 'Movie.2160p', '4K'), rel(2, 'Movie.1080p')]
        self.assertEqual([r['hash'] for r in rank.autoplay_candidates(rows, 1080, 0)], [H(2)])
        self.assertEqual(rank.autoplay_candidates(rows, 2160, 0)[0]['hash'], H(1))

    def test_merge_by_hash(self):
        rows = [rel(1, 'A', seeders=5, provider='bitsearch'), rel(1, 'A', seeders=40, provider='torrentio'), dict(rel(2, 'B'), hash='nothash')]
        m = rank.merge(rows)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]['seeders'], 40)
        self.assertEqual(sorted(m[0]['providers']), ['bitsearch', 'torrentio'])

    def test_label(self):
        self.assertIn('1080p', rank.label(rel(1, 'Movie.1080p.BluRay.x265-RARBG', size=1.7)))
        self.assertIn('RARBG', rank.label(rel(1, 'Movie.1080p.BluRay.x265-RARBG')))


class Picking(unittest.TestCase):
    F = lambda self, i, p, b: {'id': i, 'path': p, 'bytes': b}

    def test_movie_largest_video_not_sample(self):
        files = [self.F(1, '/Movie/Sample/sample.mkv', 50), self.F(2, '/Movie/Movie.mkv', 9000), self.F(3, '/Movie/info.nfo', 1)]
        self.assertEqual(pick_file(files)['id'], 2)

    def test_episode_in_season_pack(self):
        files = [self.F(i, '/Show.S02/Show.S02E%02d.1080p.mkv' % i, 1000 + i) for i in range(1, 9)]
        self.assertEqual(pick_file(files, 2, 5)['id'], 5)
        self.assertEqual(pick_file(files, 2, 10 - 2)['id'], 8)  # E08 is not confused with E8x

    def test_wrong_episode_raises(self):
        files = [self.F(1, '/Show.S01E01.mkv', 10), self.F(2, '/Show.S01E02.mkv', 10)]
        with self.assertRaises(LookupError):
            pick_file(files, 1, 7)

    def test_nxn_format(self):
        files = [self.F(1, '/Show 3x04 title.mkv', 10), self.F(2, '/Show 3x14 title.mkv', 10)]
        self.assertEqual(pick_file(files, 3, 4)['id'], 1)


if __name__ == '__main__':
    unittest.main()
