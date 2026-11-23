# CineDebrid for Kodi

Netflix-style movie and TV browsing (TMDB), sources from your **CocoScrapers**, streamed through **Real-Debrid**
into Kodi's own player. Because Kodi decodes MKV, HEVC, 10-bit, HDR and DTS/TrueHD natively, nothing is converted.

## Install (once)
1. In Kodi: **Settings > System > Add-ons > Unknown sources > On**.
2. On the device running Kodi, download **`repository.cinedebrid.zip`** from this GitHub page (open the file, click **Download raw file**).
3. **Add-ons > Install from zip file >** pick `repository.cinedebrid.zip`.
4. **Add-ons > Install from repository > CineDebrid Repository > Video add-ons > CineDebrid > Install**
   (it pulls in `script.module.cocoscrapers` and `script.module.requests` if they are missing).
5. Updates arrive automatically: raise the version in `plugin.video.cinedebrid/addon.xml`, run `python tools/build_repo.py`, push.

Shortcut without a repository: **Install from zip file >** `zips/plugin.video.cinedebrid/plugin.video.cinedebrid-1.0.0.zip`
(works, but no automatic updates).

## First run
Open the add-on, then **Settings**:
- **TMDB key**: themoviedb.org/settings/api (v3 key or the long read-access token).
- **Real-Debrid API token**: real-debrid.com/apitoken.
- **Check my accounts** confirms both keys and lists the CocoScrapers providers that are enabled.

Providers are the ones you enabled in CocoScrapers' own settings.

## Using it
- Home: Continue Watching, Movies, TV Shows, My List, Search.
- Movies/TV: Trending, Popular, Top Rated, Now Playing / On The Air, Genres, By Decade.
- Press a movie or episode: it searches, ranks, and plays the best source that is already cached on Real-Debrid
  (highest quality allowed by your settings, trusted RARBG/YIFY releases first, huge REMUXes last).
- **Context menu (C / long-press) > Choose source...** shows every release with size, seeders and tags.
  Uncached releases download on Real-Debrid first, with a progress dialog.
- Resume prompt, Continue Watching with "up next", watched marks, My List.

## Settings
Auto-play on/off, highest quality to auto-play (4K/1080p/720p), largest file to auto-play, prefer streamable encodes over
REMUX, offer uncached sources, search time limit, include season packs for episodes.

## Notes
- No keys are stored in this repository; they live in your Kodi profile.
- Real-Debrid refuses some releases as "infringing"; those are skipped automatically and remembered for two hours.
- Use sources you have the right to access.

## Develop
```
python tests/test_logic.py        # ranking, merging, file picking
python tests/test_flow.py         # menus, auto-play, fallbacks, Continue Watching with a fake Kodi
python tools/build_repo.py        # rebuild zips/, addons.xml, addons.xml.md5, repository.cinedebrid.zip
```
