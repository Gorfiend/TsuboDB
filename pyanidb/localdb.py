
import sqlite3
import os
import pyanidb.hash


class LocalDB:
    def __init__(self, db_file, base_anime_folder, anidb):
        self.base_anime_folder = base_anime_folder
        self.conn = sqlite3.connect(db_file)
        self.anidb = anidb

    def __del__(self):
        # Maybe don't want this commit here...?
        self.conn.commit()
        self.conn.close()

    # def get_file(self, fid, info_codes, retry=False):

    # def add_file(self, fid, state=None, viewed=False, source=None, storage=None, other=None, edit=False, retry=False):

    # def get_anime(self, aid=None, aname=None, amask=None, retry=False):

    # def get_animedesc(self, aid, retry=False):

    def get_files(self, files):
        c = self.conn.cursor()
        unhashed = list()
        for f in files:
            rel = os.path.relpath(f, self.base_anime_folder)
            row = c.execute('SELECT * from LocalFiles WHERE Path LIKE ?', [rel]).fetchone()
            if row:
                yield FileInfo(*row)
            else:
                unhashed.append(f)

        hashed_files = pyanidb.hash.hash_files(unhashed)
        for h in hashed_files:
            fi = FileInfo(os.path.relpath(h.name, self.base_anime_folder), h.size, h.ed2k, 0, 0)
            # Need the replace in case the file got deleted previously
            c.execute('INSERT OR REPLACE INTO LocalFiles VALUES(?, ?, ?, 0, 0)', [fi.path, fi.size, fi.hash])
            yield fi

        # return hashed


class FileInfo:
    def __init__(self, path, size, hash, fid, checked):
        self.path = path
        self.size = size
        self.hash = hash
        self.fid = fid
        self.checked = checked

    def __str__(self):
        return f'{self.path}|size={self.size}|ed2k={self.hash}'
