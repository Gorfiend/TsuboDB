#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import pyanidb
import pyanidb.hash
import pyanidb.localdb

import argcomplete
import argparse
import configparser
import getpass
import os
import sys

from collections import deque

# Workaround for input/raw_input
if hasattr(__builtins__, 'raw_input'):
    input = raw_input

# Colors.
def red(x): return '\x1b[31m' + x + '\x1b[0m'
def green(x): return '\x1b[32m' + x + '\x1b[0m'
def yellow(x): return '\x1b[33m' + x + '\x1b[0m'
def blue(x): return '\x1b[34m' + x + '\x1b[0m'


# Config.
config = {}
try:
    cp = configparser.ConfigParser()
    cp.read([os.path.expanduser('~/.pyanidb.conf'), os.path.join('.', 'userData', 'pyanidb.conf')])
    for option in cp.options('pyanidb'):
        config[option] = cp.get('pyanidb', option)
except IOError as e:
    pass

# Options.

parser = argparse.ArgumentParser(description='Manage anidb files/mylist')

parser.add_argument('-u', '--username', help='AniDB username.',
                    default=config.get('username'))
parser.add_argument('-p', '--password', help='AniDB password.',
                    default=config.get('password'))

parser.add_argument('-r', '--recursive', help='Recurse into directories.',
                    action='store_true', default=False)
parser.add_argument('-s', '--suffix', help='File suffix for recursive matching.',
                    action='append', default=config.get('suffix', '').split())

parser.add_argument('-i', '--identify', help='Identify files.',
                    action='store_true', default=False)
parser.add_argument('-a', '--add', help='Add files to mylist.',
                    action='store_true', default=False)
parser.add_argument('-w', '--watched', help='Mark files watched.',
                    action='store_true', default=False)

parser.add_argument('-n', '--rename', help='Rename files.',
                    action='store_true', default=False)
parser.add_argument('-f', '--format', help='Filename format.',
                    default=config.get('format'))

parser.add_argument('--database-file', help='Database file location.',
                    default=config.get('database-file', 'userData/TsuboDB.db'))
parser.add_argument('--anime-dir', help='Anime base dir for file scanning.',
                    default=config.get('anime-dir', '.'))


parser.add_argument('paths', metavar='Path', nargs='+',
                    help='videos to process.')

argcomplete.autocomplete(parser)
args = parser.parse_args()

# Defaults.

args.identify = args.identify or args.rename
args.login = args.add or args.watched or args.identify
if not args.suffix:
    args.suffix = ['avi', 'ogm', 'mkv']
if not args.format:
    args.format = r'_[%group]_%anime_-_%epno%ver_[%CRC].%suf'

if args.login:
    if not args.username:
        args.username = input('Username: ')
    if not args.password:
        args.password = getpass.getpass()

# Input files.

files = []
remaining = deque(args.paths)
while remaining:
    name = remaining.popleft()
    if not os.access(name, os.R_OK):
        print('{0} {1}'.format(red('Invalid file:'), name))
    elif os.path.isfile(name):
        files.append(name)
    elif os.path.isdir(name):
        if not args.recursive:
            print('{0} {1}'.format(red('Is a directory:'), name))
        else:
            for sub in sorted(os.listdir(name)):
                if sub.startswith('.'):
                    continue
                sub = os.path.join(name, sub)
                if os.path.isfile(sub) and any(sub.endswith('.' + suffix) for suffix in args.suffix):
                    files.append(sub)
                elif os.path.isdir(sub):
                    remaining.appendleft(sub)

if not files:
    print(blue('Nothing to do.'))
    sys.exit(0)

# Authorization.

if args.login:
    a = pyanidb.AniDB(args.username, args.password)
    try:
        a.auth()
        print('{0} {1}'.format(blue('Logged in as user:'), args.username))
    except pyanidb.AniDBUserError:
        print(red('Invalid username/password.'))
        sys.exit(1)
    except pyanidb.AniDBTimeout:
        print(red('Connection timed out.'))
        sys.exit(1)
    except pyanidb.AniDBError as e:
        print('{0} {1}'.format(red('Fatal error:'), e))
        sys.exit(1)
else:
    a = None

# Hashing.

hashed = 0
unknown = 0

db = pyanidb.localdb.LocalDB(args.database_file, args.anime_dir, a)


for file in db.get_files(files):
    print(f'{blue("File:")} {file}')
    fid = (file.size, file.hash)
    hashed += 1

    try:

        # Identify.

        if args.identify:
            info = a.get_file(fid, ('gtag', 'kanji', 'epno', 'state', 'epkanji', 'crc32', 'filetype'), True)
            fid = int(info['fid'])
            print(f'{green("Identified:")} [{info["gtag"]}] {info["kanji"]} - {info["epno"]} - {info["epkanji"]}')

        # Renaming.

        if args.rename:
            s = args.format
            rename_data = {
                'group': info['gtag'],
                'anime': info['romaji'],
                'epno': info['epno'],
                'ver': {0: '', 4: 'v2', 8: 'v3', 16: 'v4', 32: 'v5'}[(int(info['state']) & 0x3c)],
                'crc': info['crc32'],
                'CRC': info['crc32'].upper(),
                'suf': info['filetype']}
            for name, value in rename_data.items():
                s = s.replace(r'%' + name, value)
            if s[0] == '_':
                s = s[1:].replace(' ', '_')
            s = s.replace('/', '_')

            print('{0} {1}'.format(yellow('Renaming to:'), s))
            os.rename(file.name, os.path.join(os.path.split(file.name)[0], s))

        # Adding.

        if args.add:
            a.add_file(fid, viewed=args.watched, retry=True)
            print(green('Added to mylist.'))

        # Watched.

        elif args.watched:
            a.add_file(fid, viewed=True, edit=True, retry=True)
            print(green('Marked watched.'))

    except pyanidb.AniDBUnknownFile:
        print(red('Unknown file.'))
        unknown += 1

    except pyanidb.AniDBNotInMylist:
        print(red('File not in mylist.'))

# Finished.

print(blue(f'Hashed {hashed} files{f", {unknown} unknown" if unknown else ""}.'))
