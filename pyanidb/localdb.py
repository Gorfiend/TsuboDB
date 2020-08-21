
import sqlite3
import os

from pyanidb.api import AniDB
from pyanidb.hash import hash_files
from pyanidb.types import *

from typing import Iterable, Optional


class LocalDB:
    def __init__(self, db_file: str, base_anime_folder: str, anidb: Optional[AniDB]):
        self.base_anime_folder = base_anime_folder
        self.conn = sqlite3.connect(db_file)
        self.anidb = anidb

    def __del__(self):
        # Maybe don't want this commit here...?
        self.conn.commit()
        self.conn.close()

    def get_file(self, local: LocalFileInfo) -> FileInfo:
        # , ('gtag', 'kanji', 'epno', 'state', 'epkanji', 'crc32', 'filetype'), True
        if not self.anidb:
            print('ERR: needed to log in to AniDB!')
            raise AniDBError()

        info = self.anidb.get_file(local, ('eid', 'aid', 'english', 'romaji', 'kanji', 'epname', 'epromaji', 'epkanji', 'epno', 'quality', 'length',
            'dublang', 'sublang', 'vres', 'filetype'), True)
        print(info)
        local.fid = Fid(info['fid'])
        local.checked = True
        return FileInfo(local, Eid(info['eid']), Aid(info['aid']))


    def add_file(self, fid, state=None, viewed=False, source=None, storage=None, other=None, edit=False, retry=False):
        pass

    # def get_anime(self, aid=None, aname=None, amask=None, retry=False):

    def get_files(self, files: Iterable[str]) -> Iterable[LocalFileInfo]:
        c = self.conn.cursor()
        unhashed = list()
        for f in files:
            rel = os.path.relpath(f, self.base_anime_folder)
            row = c.execute('SELECT * from LocalFiles WHERE Path LIKE ?', [rel]).fetchone()
            if row:
                yield LocalFileInfo(*row)
            else:
                unhashed.append(f)

        hashed_files = hash_files(unhashed)
        for h in hashed_files:
            fi = LocalFileInfo(os.path.relpath(h.name, self.base_anime_folder), h.size, h.ed2k, Fid(0), False)
            # Need the replace in case the file got deleted previously
            c.execute('INSERT OR REPLACE INTO LocalFiles VALUES(?, ?, ?, 0, 0)', [fi.path, fi.size, fi.ed2k])
            yield fi
