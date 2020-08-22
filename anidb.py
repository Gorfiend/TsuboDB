#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import tsubodb
import tsubodb.api
import tsubodb.hash
import tsubodb.localdb

import argcomplete
import argparse
import configparser
import getpass
import os
import subprocess
import sys

from collections import deque

from typing import Iterable, Optional

# Colors.
def red(x): return '\x1b[31m' + x + '\x1b[0m'
def green(x): return '\x1b[32m' + x + '\x1b[0m'
def yellow(x): return '\x1b[33m' + x + '\x1b[0m'
def blue(x): return '\x1b[34m' + x + '\x1b[0m'

def main():
    # Config.
    config = {}
    try:
        cp = configparser.ConfigParser()
        cp.read([os.path.expanduser('~/.config/tsubodb/tsubodb.conf')])
        for option in cp.options('tsubodb'):
            config[option] = cp.get('tsubodb', option)
    except IOError as e:
        pass

    # Options.

    parser = argparse.ArgumentParser(description='Manage anidb files/mylist')

    parser.add_argument('-u', '--username', help='AniDB username.', default=config.get('username'))
    parser.add_argument('-p', '--password', help='AniDB password.', default=config.get('password'))

    parser.add_argument('-r', '--recursive', help='Recurse into directories.', action='store_true')
    parser.add_argument('-s', '--suffix', help='File suffix for recursive matching.',
                        action='append', default=config.get('suffix', '').split())

    parser.add_argument('-i', '--identify', help='Identify files.', action='store_true')
    parser.add_argument('-a', '--add', help='Add files to mylist.', action='store_true')
    parser.add_argument('-w', '--watched', help='Mark files watched.', action='store_true')
    parser.add_argument('--fetch-mylist', help='Re-download mylist into db.', action='store_true')

    parser.add_argument('--database-file', help='Database file location.',
                        default=config.get('database-file', os.path.expanduser('~/.config/tsubodb/TsuboDB.db')))
    parser.add_argument('--anime-dir', help='Anime base dir for file scanning.',
                        default=config.get('anime-dir', '.'))

    parser.add_argument('--playnext', help='Play next episode then mark watched.', action='store_true')
    
    parser.add_argument('--fill-database', help='Fill any missing files or Mylists', action='store_true')
    parser.add_argument('--fill-mylist', help='Get MyList for all files.', action='store_true')


    parser.add_argument('paths', metavar='Path', nargs='*', help='videos to process.')

    argcomplete.autocomplete(parser)
    args = parser.parse_args()


    os.chdir(args.anime_dir)


    # Defaults.

    args.login = args.add or args.watched or args.identify
    if not args.suffix:
        args.suffix = ['avi', 'ogm', 'mkv', 'mp4']

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


    a = tsubodb.api.AniDB(args.username, args.password)
    db = tsubodb.localdb.LocalDB(args.database_file, args.anime_dir, a)

    try:
        if files:
            for file in db.get_local_files(files):
                print(f'{blue("File:")} {file}')

                try:
                    # Identify.
                    info = db.get_file(file)
                    if not info:
                        print(f'{red("Unknown:")} {file}')
                        continue

                    print(f'{green("Identified:")} {info.aname_k} - {info.epno} - {info.epname_k}')

                    # Watched.
                    if args.watched:
                        db.mark_watched(info.fid)
                        print(green('Marked watched.'))

                    if args.fetch_mylist:
                        db.fetch_mylist(info.fid)

                except tsubodb.types.AniDBUnknownFile:
                    print(red('Unknown file.'))

                except tsubodb.types.AniDBNotInMylist:
                    print(red('File not in mylist.'))

        if args.fill_database:
            db.fill_files()
            db.fill_mylist()

        if args.fill_mylist:
            db.fill_mylist()

        if args.playnext:
            playnext = db.get_playnext_file()
            if not playnext:
                candidates = db.get_potential_playnext()
                for i, c in enumerate(candidates):
                    print(i, c.aname_k, c.epno)
                while True:
                    choice = input('Select next series to watch:')
                    try:
                        playnext = candidates[int(choice)]
                        break
                    except (ValueError, IndexError):
                        print('Invalid choice! (ctrl-c to cancel)')
            if playnext:
                rel = os.path.relpath(db.base_anime_folder, os.getcwd())
                rel = os.path.join(rel, playnext.path)
                print(rel)
                print(os.getcwd())
                subprocess.run(['mpv', rel])
                input('Mark watched? (ctrl-c to cancel)')
                db.mark_watched(playnext.fid)
                db.increment_playnext()


    except tsubodb.types.AniDBUserError:
        print(red('Invalid username/password.'))
        sys.exit(1)
    except tsubodb.types.AniDBTimeout:
        print(red('Connection timed out.'))
        sys.exit(1)
    except tsubodb.types.AniDBError as e:
        print('{0} {1}'.format(red('Fatal error:'), e))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
