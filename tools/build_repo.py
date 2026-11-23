#!/usr/bin/env python3
"""Build the Kodi repository from the add-on folders next to this script's parent:

    python tools/build_repo.py            # writes zips/<id>/<id>-<version>.zip, addons.xml, addons.xml.md5

Commit the result and push; Kodi reads addons.xml + zips straight from raw.githubusercontent.com.
Only the files Kodi needs go into a zip (no tests, caches or git data).
"""
import hashlib
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ADDONS = ['plugin.video.cinedebrid', 'repository.cinedebrid']
SKIP_DIRS = {'__pycache__', '.git', '.idea'}
SKIP_EXT = {'.pyc', '.pyo'}


def addon_info(folder):
    root = ET.parse(os.path.join(ROOT, folder, 'addon.xml')).getroot()
    return root.attrib['id'], root.attrib['version']


def build_zip(folder):
    aid, ver = addon_info(folder)
    out_dir = os.path.join(ROOT, 'zips', aid)
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.endswith('.zip'):
            os.remove(os.path.join(out_dir, old))
    out = os.path.join(out_dir, '%s-%s.zip' % (aid, ver))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, files in os.walk(os.path.join(ROOT, folder)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in sorted(files):
                if os.path.splitext(f)[1] in SKIP_EXT:
                    continue
                full = os.path.join(dirpath, f)
                z.write(full, os.path.join(aid, os.path.relpath(full, os.path.join(ROOT, folder))).replace(os.sep, '/'))
    # Kodi shows icon/fanart of repository add-ons from the zips folder too
    for asset in ('icon.png', 'fanart.jpg'):
        src = os.path.join(ROOT, folder, asset)
        if os.path.exists(src):
            with open(src, 'rb') as a, open(os.path.join(out_dir, asset), 'wb') as b:
                b.write(a.read())
    return out


def build_personal(env_path):
    """A private zip with the owner's keys inside (resources/lib/embedded.py). Never committed: personal/ is gitignored,
    and the keys are added to the zip only, never to the working tree."""
    keys = {}
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                keys[k] = v
    if not keys.get('TMDB_KEY') or not keys.get('RD_TOKEN'):
        sys.exit('TMDB_KEY and RD_TOKEN must both be in ' + env_path)
    aid, ver = addon_info('plugin.video.cinedebrid')
    out_dir = os.path.join(ROOT, 'personal')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, '%s-%s-personal.zip' % (aid, ver))
    base = os.path.join(ROOT, 'plugin.video.cinedebrid')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in sorted(files):
                if os.path.splitext(fn)[1] in SKIP_EXT or fn == 'embedded.py':
                    continue
                full = os.path.join(dirpath, fn)
                z.write(full, os.path.join(aid, os.path.relpath(full, base)).replace(os.sep, '/'))
        z.writestr('%s/resources/lib/embedded.py' % aid,
                   '# personal build: private keys, do not share this zip\nTMDB_KEY = %r\nRD_TOKEN = %r\n' % (keys['TMDB_KEY'], keys['RD_TOKEN']))
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<html><head><title>Index of /</title></head><body><h1>Index of /</h1><pre>\n<a href="%s">%s</a>\n</pre></body></html>\n'
                % (os.path.basename(out), os.path.basename(out)))
    print('built private', os.path.relpath(out, ROOT))


def main():
    if '--personal' in sys.argv:
        i = sys.argv.index('--personal')
        return build_personal(sys.argv[i + 1] if len(sys.argv) > i + 1 else os.path.join(ROOT, '.env'))
    blocks = []
    for folder in ADDONS:
        z = build_zip(folder)
        print('built', os.path.relpath(z, ROOT))
        with open(os.path.join(ROOT, folder, 'addon.xml'), encoding='utf-8') as f:
            xml = f.read()
        blocks.append(re.sub(r'^<\?xml[^>]*\?>\s*', '', xml).strip())
    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + '\n'.join(blocks) + '\n</addons>\n'
    with open(os.path.join(ROOT, 'addons.xml'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(addons_xml)
    with open(os.path.join(ROOT, 'addons.xml.md5'), 'w', encoding='ascii') as f:
        f.write(hashlib.md5(addons_xml.encode('utf-8')).hexdigest())
    # a copy of the repository add-on at the root for a one-click "install from zip" download
    repo_id, repo_ver = addon_info('repository.cinedebrid')
    src = os.path.join(ROOT, 'zips', repo_id, '%s-%s.zip' % (repo_id, repo_ver))
    with open(src, 'rb') as a, open(os.path.join(ROOT, '%s.zip' % repo_id), 'wb') as b:
        b.write(a.read())
    print('wrote addons.xml, addons.xml.md5 and', '%s.zip' % repo_id)


if __name__ == '__main__':
    sys.exit(main())
