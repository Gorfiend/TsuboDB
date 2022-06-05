
import time
import sqlite3

from tsubodb.types import *

from typing import Dict, Iterable, Iterator, List, Tuple, Optional, Union


class _Query:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_local_file(self, path: DbRelPath, size: int, ed2k: HashStr) -> None:
        self.conn.execute('INSERT OR REPLACE INTO LocalFiles VALUES(?, ?, ?, 0, 0)', [path, size, ed2k])

    def insert_file_from_anidb(self, info: Dict[str, str]) -> None:
        self.conn.execute(
'''
INSERT OR REPLACE INTO Files
VALUES(:fid, :eid, :aid, :english, :romaji, :kanji, :epno, :epname, :epromaji, :epkanji)
''', info)

    def insert_mylist(self, mylist: MyList) -> None:
        self.conn.execute(
'''
INSERT OR REPLACE INTO MyList
VALUES(:lid, :fid, :eid, :aid, :gid, :date, :state, :viewdate)
''', mylist.__dict__)

    def mylist_mark_watched(self, mylist: MyList) -> None:
        timestamp = int(time.time())
        self.conn.execute('UPDATE Mylist SET viewdate = ? WHERE lid = ?', [timestamp, mylist.lid])

    def delete_local(self, path: DbRelPath) -> None:
        self.conn.execute('DELETE FROM LocalFiles WHERE path LIKE ?', [path])

    def force_recheck(self, path: DbRelPath) -> None:
        self.conn.execute('UPDATE LocalFiles SET checked = 0 WHERE path LIKE ?', [path])

    def get_local_file_from_path(self, path: DbRelPath) -> Optional[LocalFileInfo]:
        row = self.conn.execute('SELECT * from LocalFiles WHERE path LIKE ?', [path]).fetchone()
        if row:
            return LocalFileInfo(*row)
        return None

    def get_file_from_local(self, local: LocalFileInfo) -> Optional[FileInfo]:
        row = self.conn.execute('SELECT * from Files WHERE fid = ?', [local.fid]).fetchone()
        if row:
            return FileInfo(local.path, local.size, local.ed2k, *row)
        return None

    def update_local_checked(self, local: LocalFileInfo) -> None:
        self.conn.execute(
'''
UPDATE LocalFiles
SET checked = 1, fid = ?
WHERE path LIKE ?
''', [local.fid, local.path])

    def get_mylist_from_fid(self, fid: Fid) -> Optional[MyList]:
        row = self.conn.execute('SELECT * from MyList WHERE fid = ?', [fid]).fetchone()
        if row:
            return MyList(*row)
        return None

    def get_unchecked_local_files(self) -> Iterator[LocalFileInfo]:
        c = self.conn.cursor()
        for row in c.execute('SELECT * FROM LocalFiles WHERE checked == 0'):
            yield LocalFileInfo(*row)
        c.close()

    def get_fids_not_in_mylist(self) -> Iterator[Fid]:
        c = self.conn.cursor()
        for row in c.execute('''
SELECT fid
FROM Files
LEFT JOIN MyList USING(fid)
WHERE Mylist.date IS NULL'''):
            yield Fid(row[0])
        c.close()

    def get_playnext_file(self) -> Optional[LocalEpisodeInfo]:
        row = self.conn.execute('''
SELECT LocalEpisodeInfo.*
FROM PlayNext
LEFT JOIN LocalEpisodeInfo USING(aid, epno)''').fetchone()
        if row:
            return LocalEpisodeInfo(*row)
        return None

    def get_playnext_for_episode(self, aid: Aid, epno: str) -> Optional[LocalEpisodeInfo]:
        row = self.conn.execute('''
SELECT *
FROM LocalEpisodeInfo
WHERE aid == ? AND epno REGEXP ?''', [aid, epno]).fetchone()
        if row:
            return LocalEpisodeInfo(*row)
        return None

    def insert_playnext(self, aid: Aid, epno: str) -> None:
        self.conn.execute('INSERT INTO PlayNext VALUES(?, ?)', [aid, epno])

    def delete_playnext(self) -> None:
        self.conn.execute('DELETE FROM PlayNext')

    def get_potential_playnext(self) -> Iterator[LocalEpisodeInfo]:
        """
        Find series (defined by unique aid+epno code) that have not been watched
        Return the earliest epno for each of those
        Ignoring C and T code (credits/trailers)
        """
        c = self.conn.cursor()
        for row in c.execute('''
SELECT LocalEpisodeInfo.*, MIN(epno) as epnomin,
            CASE
                WHEN epno GLOB '[A-Z]*' THEN
                    substr(epno, 1, 1)
                ELSE
                    ''
                END epcode
FROM LocalEpisodeInfo
WHERE NOT viewed AND epcode NOT LIKE "C" AND epcode NOT LIKE "T"
GROUP BY aid, epcode
ORDER BY aid ASC, epno ASC'''):
            yield LocalEpisodeInfo(*row[:13])
        c.close()
