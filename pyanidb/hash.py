import threading
import time
import os
import hashlib
import binascii

from pyanidb.types import *
from typing import Iterable, List


class Ed2k:
    def __init__(self):
        self.md4_partial = hashlib.new('md4')
        self.md4_final = hashlib.new('md4')
        self.size_total = 0

    def update(self, data):
        pos = 0
        while pos < len(data):
            if (not (self.size_total % 9728000)) and self.size_total:
                self.md4_final.update(self.md4_partial.digest())
                self.md4_partial = hashlib.new('md4')
            size = min(len(data) - pos, 9728000 - (self.size_total % 9728000))
            self.md4_partial.update(data[pos:pos + size])
            pos += size
            self.size_total += size

    def hexdigest(self):
        if self.size_total > 9728000:
            self.md4_final.update(self.md4_partial.digest())
            return self.md4_final.hexdigest()
        return self.md4_partial.hexdigest()


class Crc32:
    def __init__(self):
        self.s = 0

    def update(self, data):
        self.s = binascii.crc32(data, self.s)

    def hexdigest(self):
        return '{0:08x}'.format(self.s & 0xffffffff)



class Hash:
    def __init__(self, filename, algorithms):
        h = Ed2k()

        f = open(filename, 'rb')
        data = f.read(131072)
        while data:
            h.update(data)
            data = f.read(131072)
        self.ed2k = h.hexdigest()


class HashedFile:
    def __init__(self, name, algorithms):
        self.name = name
        self.size = os.path.getsize(name)
        self.mtime = os.path.getmtime(name)
        h = Hash(name, algorithms)
        self.ed2k = HashStr(h.ed2k)


class Hashthread(threading.Thread):
    def __init__(self, filelist, hashlist: Iterable[HashedFile], algorithms, *args, **kwargs):
        self.filelist = filelist
        self.hashlist = hashlist
        self.algorithms = algorithms
        threading.Thread.__init__(self, *args, **kwargs)

    def run(self):
        try:
            while 1:
                f = self.filelist.pop(0)
                self.hashlist.append(HashedFile(f, self.algorithms))
        except IndexError:
            return


def hash_files(files, algorithms=('ed2k',), num_threads=1) -> Iterable[HashedFile]:
    hashlist: List[HashedFile] = []
    threads = []
    for x in range(num_threads):
        thread = Hashthread(files, hashlist, algorithms)
        thread.start()
        threads.append(thread)
    while hashlist or any([thread.isAlive() for thread in threads]):
        try:
            yield hashlist.pop(0)
        except IndexError:
            time.sleep(0.1)
    raise StopIteration
