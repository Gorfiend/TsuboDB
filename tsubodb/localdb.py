
import sqlite3
import os

from tsubodb.api import AniDB
from tsubodb.hash import hash_files
from tsubodb.types import *
from tsubodb._query import _Query

from typing import Dict, Iterable, Iterator, List, Tuple, Optional, Union


class LocalDB:
    def __init__(self, db_file: str, base_anime_folder: str, anidb: AniDB):
        self.base_anime_folder = base_anime_folder
        self.conn = sqlite3.connect(db_file)
        self.anidb = anidb
        self.query = _Query(self.conn)

    def __del__(self):
        # Maybe don't want this commit here...?
        self.conn.commit()
        self.conn.close()

    @staticmethod
    def _mylist_from_anidb(data) -> MyList:
        return MyList(data[0], data[1], data[2], data[3], data[4], int(data[5]), int(data[6]), int(data[7]))

    def get_file(self, local: LocalFileInfo) -> Optional[FileInfo]:
        file = self.query.get_file_from_local(local)
        if file or local.checked:
            return file

        try:
            info = self.anidb.get_file(local, ('eid', 'aid', 'english', 'romaji', 'kanji', 'epname', 'epromaji', 'epkanji', 'epno'), True)
            local.fid = Fid(info['fid'])
            local.checked = True
        except AniDBUnknownFile:
            local.checked = True

        self.query.update_local_checked(local)

        if not local.fid:
            return None

        self.query.insert_file_from_anidb(info)

        self.get_mylist(local.fid)  # Will add mylist if needed

        return self.query.get_file_from_local(local)

    def get_mylist(self, fid: Fid, viewed=False) -> Optional[MyList]:
        mylist = self.query.get_mylist_from_fid(fid)
        if (mylist):
            return mylist
        code, data = self.anidb.add_file(fid, storage=1, viewed=viewed)
        if code == 210:
            lid = Lid(data[0])
            data = self.anidb.get_mylist_lid(lid)
        mylist = LocalDB._mylist_from_anidb(data)
        self.query.insert_mylist(mylist)
        return mylist

    def mark_watched(self, fid: Fid) -> None:
        mylist = self.get_mylist(fid, viewed=True)
        if mylist and not mylist.watched:
            self.anidb.mark_watched(mylist.lid)
            data = self.anidb.get_mylist_lid(mylist.lid)
            mylist = LocalDB._mylist_from_anidb(data)
            self.query.insert_mylist(mylist)

    def fetch_mylist(self, fid: Fid) -> None:
        mylist = self.query.get_mylist_from_fid(fid)
        if (mylist):
            data = self.anidb.get_mylist_lid(mylist.lid)
        else:
            data = self.anidb.get_mylist(fid)
        mylist = LocalDB._mylist_from_anidb(data)
        self.query.insert_mylist(mylist)

    def fill_files(self) -> None:
        for local in self.query.get_unchecked_local_files():
            self.get_file(local)

    def fill_mylist(self) -> None:
        for fid in self.query.get_fids_not_in_mylist():
            self.get_mylist(fid)

    def get_local_files(self, files: Iterable[str]) -> Iterable[LocalFileInfo]:
        c = self.conn.cursor()
        unhashed = list()
        for f in files:
            real = os.path.realpath(f)
            rel = os.path.relpath(real, self.base_anime_folder)
            local = self.query.get_local_file_from_path(rel)
            if local:
                yield local
            else:
                unhashed.append(real)

        hashed_files = hash_files(unhashed)
        for h in hashed_files:
            local = LocalFileInfo(os.path.relpath(h.name, self.base_anime_folder), h.size, h.ed2k)
            self.query.insert_local_file(local.path, local.size, local.ed2k)
            yield local

    def get_playnext_file(self) -> Optional[PlaynextFile]:
        # TODO might want to support multiple series...?
        return self.query.get_playnext_file()

    def increment_playnext(self, playnext: PlaynextFile) -> Optional[PlaynextFile]:
        try:
            code = ''
            epnum = int(playnext.epno)
        except ValueError:
            code = playnext.epno[0]
            epnum = int(playnext.epno[1:])
        epnum += 1
        new_epno = f'{code}{epnum:0{2}}'
        nextInfo = self.query.get_playnext_for_episode(playnext.aid, new_epno)
        if nextInfo:
            self.query.update_playnext(playnext, new_epno)
            return nextInfo
        else:
            self.query.delete_playnext(playnext)
            return None

    def get_potential_playnext(self) -> Iterator[PlaynextFile]:
        return self.query.get_potential_playnext()
