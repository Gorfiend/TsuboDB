
import typing

Fid = typing.NewType('Fid', int)  # AniDB file ID
Eid = typing.NewType('Eid', int)  # AniDB episode ID
Aid = typing.NewType('Aid', int)  # AniDB anime ID
Lid = typing.NewType('Lid', int)  # AniDB mylist ID
Gid = typing.NewType('Gid', int)  # AniDB group ID
HashStr = typing.NewType('HashStr', str)

class LocalFileInfo:
    def __init__(self, path: str, size: int, ed2k: HashStr, fid: Fid = Fid(0), checked: bool = False):
        self.path = path
        self.size = size
        self.ed2k = ed2k
        self.fid = fid
        self.checked = bool(checked)  # needed for making this from sqlite query - might be a better way

    def __str__(self) -> str:
        return f'{self.path}|size={self.size}|ed2k={self.ed2k}|{self.checked}'


class FileInfo:
    def __init__(self, path:str, size: int, ed2k: str, fid: Fid, eid: Eid, aid: Aid,
            aname_e: str, aname_r: str, aname_k: str, epno: str, epname_e: str, epname_r: str, epname_k: str):
        self.path = path
        self.size = size
        self.ed2k = ed2k
        self.fid = fid
        self.eid = eid
        self.aid = aid
        self.aname_e = aname_e
        self.aname_r = aname_r
        self.aname_k = aname_k
        self.epno = epno
        self.epname_e = epname_e
        self.epname_r = epname_r
        self.epname_k = epname_k

    def __str__(self) -> str:
        return f'{self.path}|size={self.size}|ed2k={self.ed2k}'


class MyList:
    def __init__(self, lid: Lid, fid: Fid, eid: Eid, aid: Aid, gid: Gid, date: int, state: int, viewdate: int):
        self.lid = lid
        self.fid = fid
        self.eid = eid
        self.aid = aid
        self.gid = gid
        self.date = date
        self.state = state
        self.viewdate = viewdate
        self.watched = viewdate > 0


class PlaynextFile():
    def __init__(self, aid: Aid, fid: Fid, path: str, aname_k: str, epname_k: str, epno: str):
        self.aid = aid
        self.fid = fid
        self.path = path
        self.aname_k = aname_k
        self.epname_k = epname_k
        self.epno = epno

    def __str__(self) -> str:
        return f'{self.aname_k} - {self.epno} - {self.epname_k}'


# AniDB exceptions

class AniDBError(Exception):
    pass


class AniDBTimeout(AniDBError):
    pass


class AniDBLoginError(AniDBError):
    pass


class AniDBUserError(AniDBLoginError):
    pass


class AniDBReplyError(AniDBError):
    pass


class AniDBUnknownFile(AniDBError):
    pass


class AniDBNotInMylist(AniDBError):
    pass


class AniDBUnknownAnime(AniDBError):
    pass


class AniDBUnknownDescription(AniDBError):
    pass


class AniDBNoWishlist(AniDBError):
    pass
