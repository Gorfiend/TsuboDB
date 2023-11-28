import threading
import time
import os
import hashlib

from tsubodb.types import *
from typing import Any, Iterable, List


class Ed2k:
    def __init__(self) -> None:
        self.md4_partial = hashlib.new('md4')
        self.md4_final = hashlib.new('md4')
        self.size_total = 0

    def update(self, data: bytes) -> None:
        pos = 0
        while pos < len(data):
            if (not (self.size_total % 9728000)) and self.size_total:
                self.md4_final.update(self.md4_partial.digest())
                self.md4_partial = hashlib.new('md4')
            size = min(len(data) - pos, 9728000 - (self.size_total % 9728000))
            self.md4_partial.update(data[pos:pos + size])
            pos += size
            self.size_total += size

    def hexdigest(self) -> str:
        if self.size_total > 9728000:
            self.md4_final.update(self.md4_partial.digest())
            return self.md4_final.hexdigest()
        return self.md4_partial.hexdigest()


class Hash:
    def __init__(self, filename: str):
        h = Ed2k()

        f = open(filename, 'rb')
        data = f.read(131072)
        while data:
            h.update(data)
            data = f.read(131072)
        self.ed2k = h.hexdigest()


class HashedFile:
    def __init__(self, name: str):
        self.name = name
        self.size = os.path.getsize(name)
        self.mtime = os.path.getmtime(name)
        h = Hash(name)
        self.ed2k = HashStr(h.ed2k)


class Hashthread(threading.Thread):
    def __init__(self, filelist: List[str], hashlist: List[HashedFile], *args: Any, **kwargs: Any):
        self.filelist = filelist
        self.hashlist = hashlist
        threading.Thread.__init__(self, *args, daemon=True, **kwargs)

    def run(self) -> None:
        try:
            while 1:
                f = self.filelist.pop(0)
                self.hashlist.append(HashedFile(f))
        except IndexError:
            return


def hash_files(files: List[str], num_threads: int=1) -> Iterable[HashedFile]:
    hashlist: List[HashedFile] = []
    threads = []
    for x in range(num_threads):
        thread = Hashthread(files, hashlist)
        thread.start()
        threads.append(thread)
    while hashlist or any([thread.is_alive() for thread in threads]):
        try:
            yield hashlist.pop(0)
        except IndexError:
            time.sleep(0.1)
    return
