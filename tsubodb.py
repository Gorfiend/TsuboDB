#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import configparser
import getpass
import os
import subprocess
import sys

import argcomplete

import tsubodb.api
import tsubodb.hash
import tsubodb.localdb
from tsubodb.types import *

# Colors.
def red(text: str) -> str:
    return '\x1b[31m' + text + '\x1b[0m'

def green(text: str) -> str:
    return '\x1b[32m' + text + '\x1b[0m'

def yellow(text: str) -> str:
    return '\x1b[33m' + text + '\x1b[0m'

def blue(text: str) -> str:
    return '\x1b[34m' + text + '\x1b[0m'


def main() -> None:
    # Config.
    config = {}
    try:
        config_parser = configparser.ConfigParser()
        config_parser.read([os.path.expanduser('~/.config/tsubodb/tsubodb.conf')])
        for option in config_parser.options('tsubodb'):
            config[option] = config_parser.get('tsubodb', option)
    except IOError:
        pass

    # Options.

    parser = argparse.ArgumentParser(description='Manage anidb files/mylist')

    parser.add_argument('-u', '--username', help='AniDB username.', default=config.get('username'))
    parser.add_argument('-p', '--password', help='AniDB password.', default=config.get('password'))

    parser.add_argument('-s', '--suffix', help='File suffixes to include when scanning directories.',
                        action='append', default=config.get('suffix', '').split())

    parser.add_argument('-w', '--watched', help='Mark files watched.', action='store_true')
    parser.add_argument('--fetch-mylist', help='Re-download mylist into db.', action='store_true')

    parser.add_argument('--database-file', help='Database file location.',
                        default=config.get('database-file', os.path.expanduser('~/.config/tsubodb/TsuboDB.db')))
    parser.add_argument('--anime-dir', help='Anime base dir for file scanning.',
                        default=config.get('anime-dir', '.'))

    parser.add_argument('--playnext', help='Play next episode then mark watched.', action='store_true')
    parser.add_argument('--play', help='Choose an unfinished anime and watch the next unwatched episode in it.', action='store_true')

    parser.add_argument('--scan', help='Scan dir for new files, and import them. Defaults to anime-dir, or specify.',
                        action='append', nargs='?', const=None, default=[])
    parser.add_argument('--force-rehash', help='Force rehashing files for scan.', action='store_true')
    parser.add_argument('--force-recheck', help='Force rechecking with anidb files for scan (use after adding files to anidb through Avdump2)', action='store_true')
    parser.add_argument('--fill-database', help='Fill any missing files or Mylists', action='store_true')
    parser.add_argument('--fill-mylist', help='Get/Add MyList for all files.', action='store_true')

    parser.add_argument('--vote', help='Rate an anime by aid.')

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if not args.suffix:
        args.suffix = ['avi', 'ogm', 'mkv', 'mp4']

    def get_username() -> str:
        if not args.username:
            args.username = input('Username: ')
        username: str = args.username
        return username

    def get_password() -> str:
        if not args.password:
            args.password = getpass.getpass()
        password: str = args.password
        return password

    # Input files.

    files = []

    for path in args.scan:
        # TODO this can cause bad paths to go into database (../../../.. prefix)
        if path is None:
            path = args.anime_dir
        for dirpath, _dirnames, filenames in os.walk(path, onerror=print):
            for file in filenames:
                if any(file.endswith('.' + suffix) for suffix in args.suffix):
                    files.append(os.path.join(dirpath, file))

    anidb = tsubodb.api.AniDB(get_username, get_password)
    db = tsubodb.localdb.LocalDB(args.database_file, args.anime_dir, anidb)

    if args.scan:
        files = [x for x in files if args.force_rehash or args.force_recheck or not db.is_file_known(x)]

    files = sorted(files)

    unknown_files = []

    os.chdir(args.anime_dir)

    try:
        if files:
            if args.force_rehash:
                db.delete_local(files)
            if args.force_recheck:
                db.force_recheck(files)

            for file in db.get_local_files(files):
                print(f'{blue("File:")} {file}')

                try:
                    # Get file, and if new add to mylist
                    info = db.get_file(file)
                    if not info:
                        print(f'{red("Unknown:")} {file}')
                        unknown_files.append(file)
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

        if args.vote:
            aid = Aid(int(args.vote))
            prompt_rate_anime(anidb, aid)

        if args.playnext:
            run_playnext(db, anidb, True)

        if args.play:
            run_playnext(db, anidb, False)

    except tsubodb.types.AniDBUserError:
        print(red('Invalid username/password.'))
        sys.exit(1)
    except tsubodb.types.AniDBTimeout:
        print(red('Connection timed out.'))
        sys.exit(1)
    except tsubodb.types.AniDBError as err:
        print('{0} {1}'.format(red('Fatal error:'), err))
        sys.exit(1)

    if unknown_files:
        print(red(f'{len(unknown_files)} unknown files:'))
        for unk in unknown_files:
            print(unk.path)
        print(red(f'{len(unknown_files)} unknown files'))

def prompt_rate_anime(anidb: tsubodb.api.AniDB, aid: Aid) -> None:
    while True:
        try:
            vote = input('Enter rating (1-10): ')
            voteNum = float(vote)
            anidb.rate_anime(aid, rating=voteNum)
            anidb.remove_wishlist(aid)
            break
        except ValueError:
            print('Invalid input!')
        except AniDBNoWishlist:
            break  # Removing it, so this is fine

def run_playnext(db: tsubodb.localdb.LocalDB, anidb: tsubodb.api.AniDB, auto_choose: bool) -> None:
    while True:
        playnext = db.get_playnext_file()
        if not auto_choose or not playnext:
            candidates = list(db.get_potential_playnext())
            for i, c in enumerate(candidates):
                print(i, c.aname_k, c.epno)
            while True:
                try:
                    choice = input('Select next series to watch: ')
                    playnext = candidates[int(choice)]
                    break
                except (ValueError, IndexError):
                    print('Invalid choice! (ctrl-c to cancel)')
                except KeyboardInterrupt:
                    return
        if playnext:
            rel = os.path.relpath(db.base_anime_folder, os.getcwd())
            rel = os.path.join(rel, playnext.path)
            print(f'{blue("Playing")}: {playnext}')
            subprocess.run(['mpv', rel], check=False)
            text = input("Hit enter to mark watched and exit, type something to continue watching, ctrl-c to exit now (don't mark watched): ")
            db.mark_watched(playnext.fid)
            next_episode = db.increment_playnext(playnext)
            if not next_episode:
                try:
                    int(playnext.epno)
                    prompt_rate_anime(anidb, playnext.aid)
                except ValueError:
                    pass  # Don't rate special episodes
            if not text:
                break

if __name__ == '__main__':
    main()
