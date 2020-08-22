
import sqlite3
import os

from pyanidb.api import AniDB
from pyanidb.hash import hash_files
from pyanidb.types import *

from typing import Iterable, Optional


class LocalDB:
    def __init__(self, db_file: str, base_anime_folder: str, anidb: AniDB):
        self.base_anime_folder = base_anime_folder
        self.conn = sqlite3.connect(db_file)
        self.anidb = anidb

    def __del__(self):
        # Maybe don't want this commit here...?
        self.conn.commit()
        self.conn.close()

    @staticmethod
    def _mylist_from_anidb(data) -> MyList:
        return MyList(data[0], data[1], data[2], data[3], data[4], int(data[5]), int(data[6]), int(data[7]))

    def _insert_mylist(self, mylist: MyList) -> None:
        self.conn.execute(
'''
INSERT OR REPLACE INTO MyList
VALUES(?, ?, ?, ?, ?, ?, ?, ?)
''', [mylist.lid, mylist.fid, mylist.eid, mylist.aid, mylist.gid, mylist.date, mylist.state, mylist.viewdate])

    def _get_file_db(self, local: LocalFileInfo) -> Optional[FileInfo]:
        row = self.conn.execute('SELECT * from Files WHERE Fid = ?', [local.fid]).fetchone()
        if row:
            return FileInfo(local.path, local.size, local.ed2k, *row)
        return None

    def get_file(self, local: LocalFileInfo) -> Optional[FileInfo]:
        file = self._get_file_db(local)
        if file or local.checked:
            return file

        try:
            info = self.anidb.get_file(local, ('eid', 'aid', 'english', 'romaji', 'kanji', 'epname', 'epromaji', 'epkanji', 'epno'), True)
            local.fid = Fid(info['fid'])
            local.checked = True
        except AniDBUnknownFile:
            local.checked = True

        self.conn.execute(
'''
UPDATE LocalFiles
SET Checked = 1, Fid = ?
WHERE Path LIKE ?
''', [local.fid, local.path])

        if not local.fid:
            return None

        self.conn.execute(
'''
INSERT INTO Files
VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', [local.fid, Eid(info['eid']), Aid(info['aid']), info['english'], info['romaji'], info['kanji'],
        info['epno'], info['epname'], info['epromaji'], info['epkanji']])

        self.get_mylist(local.fid)  # Will add mylist if needed

        return self._get_file_db(local)

    def _get_mylist_db(self, fid: Fid) -> Optional[MyList]:
        row = self.conn.execute('SELECT * from MyList WHERE fid = ?', [fid]).fetchone()
        if row:
            return MyList(*row)
        return None

    def get_mylist(self, fid: Fid, viewed=False) -> Optional[MyList]:
        mylist = self._get_mylist_db(fid)
        if (mylist):
            return mylist
        code, data = self.anidb.add_file(fid, storage=1, viewed=viewed)
        if code == 210:
            lid = Lid(data[0])
            data = self.anidb.get_mylist_lid(lid)
        mylist = LocalDB._mylist_from_anidb(data)
        self._insert_mylist(mylist)
        return mylist

    def mark_watched(self, fid: Fid) -> None:
        mylist = self.get_mylist(fid, viewed=True)
        if mylist and not mylist.watched:
            self.anidb.mark_watched(mylist.lid)
            data = self.anidb.get_mylist_lid(mylist.lid)
            mylist = LocalDB._mylist_from_anidb(data)
            self._insert_mylist(mylist)

    def update_mylist(self, fid: Fid) -> None:
        mylist = self._get_mylist_db(fid)
        if (mylist):
            data = self.anidb.get_mylist_lid(mylist.lid)
        else:
            data = self.anidb.get_mylist(fid)
        mylist = LocalDB._mylist_from_anidb(data)
        self._insert_mylist(mylist)

    def get_local_files(self, files: Iterable[str]) -> Iterable[LocalFileInfo]:
        c = self.conn.cursor()
        unhashed = list()
        for f in files:
            rel = os.path.realpath(f)
            rel = os.path.relpath(rel, self.base_anime_folder)
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

    def get_playnext_file(self) -> Optional[LocalFileInfo]:
        # TODO might want to support multiple series...?
        row = self.conn.execute('SELECT * from PlayNext').fetchone()
        if row:
            # Could probably turn this into a single query...
            file = self.conn.execute('SELECT * from Files WHERE aid == ? AND epno == ?', [row[0], row[1]]).fetchone()
            local = LocalFileInfo(*self.conn.execute('SELECT * from LocalFiles WHERE Fid == ?', [file[0]]).fetchone())
        else:
            # TODO do some stuff to find unwatched series, and provide a menu to select the next one to watch
            pass

        return local

    def increment_playnext(self) -> None:
        row = self.conn.execute('SELECT * from PlayNext').fetchone()
        try:
            code = ''
            epnum = int(row[1])
        except ValueError:
            code = row[1][0]
            epnum = int(row[1][1:])
        epnum += 1
        epno = f'{code}{epnum:0{2}}'
        if self.conn.execute('SELECT * FROM Files WHERE aid == ? AND epno LIKE ?', [row[0], epno]).fetchone:
            self.conn.execute('UPDATE PlayNext SET epno = ? WHERE aid == ? AND epno LIKE ?', [epno, row[0], row[1]])
        else:
            self.conn.execute('DELETE FROM PlayNext WHERE aid == ? AND epno LIKE ?', [row[0], epno])
