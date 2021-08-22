
import sqlite3
import os
import re

from tsubodb.api import AniDB
from tsubodb.hash import hash_files
from tsubodb.types import *
from tsubodb._query import _Query

from typing import Any, Dict, Iterable, Iterator, List, Tuple, Optional, Union


class LocalDB:
    def __init__(self, db_file: str, base_anime_folder: str, anidb: AniDB):
        self.base_anime_folder = base_anime_folder
        self.conn = sqlite3.connect(db_file)
        self.anidb = anidb

        # Add regexp function.
        self.conn.create_function('regexp', 2, lambda x, y: 1 if re.search(x,y) else 0)
        self.query = _Query(self.conn)

    def __del__(self) -> None:
        # Maybe don't want this commit here...?
        self.conn.commit()
        self.conn.close()

    def get_file(self, local: LocalFileInfo) -> Optional[FileInfo]:
        file = self.query.get_file_from_local(local)
        if file or local.checked:
            return file

        try:
            info = self.anidb.get_file(local, ('eid', 'aid', 'english', 'romaji', 'kanji', 'epname', 'epromaji', 'epkanji', 'epno'))
            local.fid = Fid(int(info['fid']))
            local.checked = True
        except AniDBUnknownFile:
            local.checked = True

        self.query.update_local_checked(local)

        if not local.fid:
            return None

        self.query.insert_file_from_anidb(info)

        self.get_mylist(local.fid)  # Will add mylist if needed

        return self.query.get_file_from_local(local)

    def get_mylist(self, fid: Fid, viewed: bool=False) -> Optional[MyList]:
        local_mylist = self.query.get_mylist_from_fid(fid)
        if (local_mylist):
            return local_mylist
        result = self.anidb.add_mylist(fid, storage=1, viewed=viewed)
        if isinstance(result, MyList):
            mylist = result
        else:
            lid = Lid(int(result[1][0]))
            mylist = self.anidb.get_mylist_lid(lid)
        self.query.insert_mylist(mylist)
        return mylist

    def mark_watched(self, fid: Fid) -> None:
        mylist = self.get_mylist(fid, viewed=True)
        if mylist and not mylist.watched:
            self.anidb.mark_watched(mylist.lid)
            self.query.mylist_mark_watched(mylist)

    def fetch_mylist(self, fid: Fid) -> None:
        local_mylist = self.query.get_mylist_from_fid(fid)
        if (local_mylist):
            mylist = self.anidb.get_mylist_lid(local_mylist.lid)
        else:
            mylist = self.anidb.get_mylist(fid)
        self.query.insert_mylist(mylist)

    def fill_files(self) -> None:
        for local in self.query.get_unchecked_local_files():
            self.get_file(local)

    def fill_mylist(self) -> None:
        for fid in self.query.get_fids_not_in_mylist():
            self.get_mylist(fid)

    def _path_to_rel(self, path: str) -> DbRelPath:
        real = os.path.realpath(path)
        return DbRelPath(os.path.relpath(real, self.base_anime_folder))

    def delete_local(self, files: Iterable[str]) -> None:
        for file in files:
            rel = self._path_to_rel(file)
            self.query.delete_local(rel)

    def force_recheck(self, files: Iterable[str]) -> None:
        for file in files:
            rel = self._path_to_rel(file)
            self.query.force_recheck(rel)

    def get_local_files(self, files: Iterable[str]) -> Iterable[LocalFileInfo]:
        c = self.conn.cursor()
        unhashed = list()
        for file in files:
            rel = self._path_to_rel(file)
            local = self.query.get_local_file_from_path(rel)
            if local:
                yield local
            else:
                unhashed.append(file)

        hashed_files = hash_files(unhashed)
        for h in hashed_files:
            local = LocalFileInfo(self._path_to_rel(h.name), h.size, h.ed2k)
            self.query.insert_local_file(local.path, local.size, local.ed2k)
            yield local

    def is_file_known(self, file: str) -> bool:
        rel = self._path_to_rel(file)
        local = self.query.get_local_file_from_path(rel)
        if not local:
            return False
        return True

    def get_playnext_file(self) -> Optional[LocalEpisodeInfo]:
        # TODO might want to support multiple series...?
        return self.query.get_playnext_file()

    def increment_playnext(self, playnext: LocalEpisodeInfo) -> Optional[LocalEpisodeInfo]:
        try:
            code = ''
            epnum = int(playnext.epno)
        except ValueError:
            code = playnext.epno[0]
            epnum = int(playnext.epno[1:])
        epnum += 1
        new_epno = f'^{code}0*{epnum}$'
        nextInfo = self.query.get_playnext_for_episode(playnext.aid, new_epno)
        self.query.delete_playnext()
        if nextInfo:
            self.query.insert_playnext(nextInfo.aid, nextInfo.epno)
            return nextInfo
        else:
            return None

    def get_potential_playnext(self) -> Iterator[LocalEpisodeInfo]:
        return self.query.get_potential_playnext()
