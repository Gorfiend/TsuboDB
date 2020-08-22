
import sqlite3
import os

from tsubodb.api import AniDB
from tsubodb.hash import hash_files
from tsubodb.types import *

from typing import Dict, Iterable, List, Tuple, Optional


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
SET checked = 1, fid = ?
WHERE path LIKE ?
''', [local.fid, local.path])

        if not local.fid:
            return None

        self.conn.execute(
'''
INSERT OR REPLACE INTO Files
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

    def fetch_mylist(self, fid: Fid) -> None:
        mylist = self._get_mylist_db(fid)
        if (mylist):
            data = self.anidb.get_mylist_lid(mylist.lid)
        else:
            data = self.anidb.get_mylist(fid)
        mylist = LocalDB._mylist_from_anidb(data)
        self._insert_mylist(mylist)

    def fill_files(self) -> None:
        c = self.conn.cursor()
        for row in c.execute('''
SELECT LocalFiles.*
FROM LocalFiles
LEFT JOIN Files USING(fid)
WHERE Files.fid IS NULL AND checked == 0'''):
            self.get_file(LocalFileInfo(*row))
        c.close()

    def fill_mylist(self):
        rows = self.conn.execute('''
SELECT fid
FROM Files
LEFT JOIN MyList USING(fid)
WHERE Mylist.date IS NULL''').fetchall()
        for r in rows:
            self.get_mylist(Fid(r[0]))


    def get_local_files(self, files: Iterable[str]) -> Iterable[LocalFileInfo]:
        c = self.conn.cursor()
        unhashed = list()
        for f in files:
            real = os.path.realpath(f)
            rel = os.path.relpath(real, self.base_anime_folder)
            row = c.execute('SELECT * from LocalFiles WHERE path LIKE ?', [rel]).fetchone()
            if row:
                yield LocalFileInfo(*row)
            else:
                unhashed.append(real)

        hashed_files = hash_files(unhashed)
        for h in hashed_files:
            fi = LocalFileInfo(os.path.relpath(h.name, self.base_anime_folder), h.size, h.ed2k, Fid(0), False)
            # Need the replace in case the file got deleted previously
            c.execute('INSERT OR REPLACE INTO LocalFiles VALUES(?, ?, ?, 0, 0)', [fi.path, fi.size, fi.ed2k])
            yield fi

    def get_playnext_file(self) -> Optional[PlaynextFile]:
        # TODO might want to support multiple series...?
        row = self.conn.execute('''
SELECT path, aname_k, epno FROM PlayNext
LEFT JOIN Files USING(aid, epno)
LEFT JOIN LocalFiles USING(fid)''').fetchone()
        if row:
            return PlaynextFile(*row)
        else:
            # TODO do some stuff to find unwatched series, and provide a menu to select the next one to watch
            return None

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

    def get_potential_playnext(self) -> Iterable[PlaynextFile]:
        rows = self.conn.execute('''
SELECT path, aname_k, epno, Files.aid
FROM Files
LEFT JOIN MyList USING(fid)
LEFT JOIN LocalFiles USING(fid)
WHERE viewdate = 0''')

        files: Dict[str, List[PlaynextFile]] = dict() 
        for row in rows:
            epcode, epnum = epinfo(row[2])
            # 1: regular episode (no prefix), 2: special ("S"), 3: credit ("C"), 4: trailer ("T"), 5: parody ("P"), 6: other ("O")
            if epcode in ('C', 'T'):
                continue
            playnext = PlaynextFile(row[0], row[1], row[2])
            files.setdefault(str(row[3]) + '-' + epcode, list()).append(playnext)
        candidates: List[PlaynextFile] = list()
        for k in files.keys():
            l = files[k]
            l.sort(key=lambda x: x.epno)
            candidates.append(l[0])
        return candidates


def epinfo(epno: str) -> Tuple[str, int]:
    try:
        code = ''
        epnum = int(epno)
    except ValueError:
        code = epno[0]
        epnum = int(epno[1:])
    return code, epnum
