
import typing

Fid = typing.NewType('Fid', int)  # AniDB file ID
Eid = typing.NewType('Eid', int)  # AniDB episode ID
Aid = typing.NewType('Aid', int)  # AniDB anime ID
Lid = typing.NewType('Lid', int)  # AniDB mylist ID
HashStr = typing.NewType('HashStr', str)

class LocalFileInfo:
    def __init__(self, path: str, size: int, ed2k: HashStr, fid: Fid, checked: bool):
        self.path = path
        self.size = size
        self.ed2k = ed2k
        self.fid = fid
        self.checked = bool(checked)  # needed for making this from sqlite query - might be a better way

    def __str__(self):
        return f'{self.path}|size={self.size}|ed2k={self.ed2k}|{self.checked}'


class FileInfo:
    def __init__(self, local: LocalFileInfo, eid: Eid, aid: Aid):
        self.path = local.path
        self.size = local.size
        self.ed2k = local.ed2k
        self.fid = local.fid
        self.eid = eid
        self.aid = aid
        # self.aname_e = aname
        # self.aname_r = epno
        # self.aname_k = epno
        # self.epno = epno
        # self.epno = epno
        # self.epno = epno
        # self.epno = epno

    def __str__(self):
        return f'{self.path}|size={self.size}|ed2k={self.ed2k}'


class Episode:
    def __init__(self, eid: Eid, aid: Aid):
        self.eid = eid
        self.aid = aid


#AniDB exceptions

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