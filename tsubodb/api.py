import socket
import time

import typing
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from tsubodb.types import *

protover = 3
client = 'tsubodb'
clientver = 3


fmask = [
    '', 'aid', 'eid', 'gid', 'lid', 'otherepisodes', 'deprecated', 'state',
    'size', 'ed2k', 'md5', 'sha1', 'crc32', '', 'vidcolordep', '',
    'quality', 'source', 'acodec', 'abitrate', 'vcodec', 'vbitrate', 'vres', 'filetype',
    'dublang', 'sublang', 'length', 'description', 'aireddate', '', '', 'anidbfilename',
    'mstate', 'mfilestate', 'mviewed', 'mviewdate', 'mstorage', 'msource', 'mother', '']
    # Note: the m* mylist infos don't seem to work (return blanks always)

amask = [
    'eptotal', 'eplast', 'year', 'type', 'relatedlist', 'relatedtype', 'categorylist', '',
    'romaji', 'kanji', 'english', 'other', 'shortname', 'synonyms', '', '',
    'epno', 'epname', 'epromaji', 'epkanji', 'eprating', 'epvotecount', '', '',
    'groupname', 'groupshortname', 'category', '', '', '', '', 'dateaidupdated']


joined_masks = fmask + amask
joined_masks.reverse()
masks = dict([(joined_masks[i], 1 << i) for i in range(len(joined_masks)) if joined_masks[i]])

ApiDict = Dict[str, str]
ApiResponse = Tuple[int, str, List[List[str]]]  # Api response code/code text/data map
ApiArgs = Dict[str, Any]  # Key/Value dict of args for an api call
ApiArgsOp = Optional[ApiArgs]  # Key/Value dict of args for an api call

class AniDB:
    def __init__(self, username: Callable[[], str], password: Callable[[], str], localport: int = 1234, server: Tuple[str, int]=('api.anidb.info', 9000)):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', localport))
        self.sock.settimeout(10)
        self.username = username
        self.password = password
        self.server = server
        self.session = ''
        self.lasttime = 0.0

    def __del__(self) -> None:
        self.logout()
        self.sock.close()

    def newver_msg(self) -> None:
        print('New version available.')

    def retry_msg(self) -> None:
        print('Connection timed out, retrying.')

    def execute(self, cmd: str, args: ApiArgsOp=None, retry: bool=True) -> ApiResponse:
        if not args:
            args = {}
        if cmd not in ('PING', 'ENCRYPT', 'ENCODING', 'AUTH', 'VERSION'):
            if not self.session:
                self.auth()
            args['s'] = self.session

        retry_count = 0
        while retry_count < 3:
            params = '&'.join(['{0}={1}'.format(*a) for a in args.items()])
            cmdData = f'{cmd} {params}\n'
            if 'pass' in args:
                paramsCen = params.replace(args['pass'], 'PASSWORD')
            else:
                paramsCen = params
            print('>', cmd, paramsCen)
            t = time.time()
            if t < self.lasttime + 2:
                time.sleep(self.lasttime + 2 - t)
            self.lasttime = time.time()
            self.sock.sendto(cmdData.encode(), 0, self.server)
            try:
                data = self.sock.recv(8192).decode().split('\n')
                print('<', data)
            except socket.timeout:
                if retry:
                    self.retry_msg()
                    time.sleep(10 ** retry_count)
                    retry_count += 1
                else:
                    raise AniDBTimeout()
            else:
                break
        code, text = data[0].split(' ', 1)
        responseData = [line.split('|') for line in data[1:-1]]
        return (int(code), text, responseData)

    def ping(self) -> bool:
        try:
            return self.execute('PING')[0] == 300
        except AniDBTimeout:
            return False

    def auth(self) -> None:
        code, text, data = self.execute('AUTH', {'user': self.username(), 'pass': self.password(), 'protover': protover,
                                                 'client': client, 'clientver': clientver, 'enc': 'utf8'})
        if code in (200, 201):
            self.session = text.split(' ', 1)[0]
            if code == 201:
                self.newver_msg()
        elif code == 500:
            raise AniDBUserError()
        else:
            raise AniDBReplyError(code, text)

    def logout(self) -> None:
        if self.session:
            try:
                self.execute('LOGOUT', {'s': self.session})
                self.session = ''
            except AniDBError:
                pass

    def get_file(self, file: LocalFileInfo, info_codes: Iterable[str]) -> ApiDict:
        args: ApiArgs
        if file.fid > 0:
            args = {'fid': file.fid}
        else:
            args = {'size': file.size, 'ed2k': file.ed2k}
        info_codes = list(info_codes)
        info_codes.sort(key=lambda x: masks[x])
        info_codes.reverse()
        info_code = sum([masks[code] for code in info_codes])
        args.update({'fmask': f'{info_code >> 32:0{10}X}', 'amask': f'{info_code  & 0xffffffff:0{8}X}'})
        while 1:
            code, text, data = self.execute('FILE', args)
            if code == 220:
                return dict([(name, data[0].pop(0)) for name in ['fid'] + info_codes])
            elif code == 320:
                raise AniDBUnknownFile()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    @staticmethod
    def _mylist_from_anidb(data: List[Any]) -> MyList:
        return MyList(data[0], data[1], data[2], data[3], data[4], int(data[5]), int(data[6]), int(data[7]))

    def get_mylist(self, fid: Fid) -> MyList:
        args = {'fid': fid}
        while 1:
            code, text, data = self.execute('MYLIST', args)
            if code == 221:
                return self._mylist_from_anidb(data[0])
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def get_mylist_lid(self, lid: Lid) -> MyList:
        args = {'lid': lid}
        while 1:
            code, text, data = self.execute('MYLIST', args)
            if code == 221:
                return self._mylist_from_anidb(data[0])
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def add_mylist(self, fid: Fid, viewed: bool=False, storage: Optional[int]=None,
            edit: bool=False) -> Union[MyList, Tuple[int, List[str]]]:
        args: ApiArgs = {'fid': fid}
        if viewed != None:
            args['viewed'] = int(bool(viewed))
        # if source != None:
        #     args['source'] = source
        if storage != None:
            args['storage'] = storage
        # if other != None:
        #     args['other'] = other
        if edit:
            args['edit'] = 1
        while 1:
            code, text, data = self.execute('MYLISTADD', args)
            if code == 310:
                return self._mylist_from_anidb(data[0])
            if code in (210, 311):
                return code, data[0]
            elif code == 320:
                raise AniDBUnknownFile()
            elif code == 411:
                raise AniDBNotInMylist()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def mark_watched(self, lid: Lid) -> None:
        args: ApiArgs = {'lid': lid}
        args['edit'] = 1
        args['viewed'] = 1
        while 1:
            code, text, data = self.execute('MYLISTADD', args)
            if code == 311:
                return
            elif code == 411:
                raise AniDBNotInMylist()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def rate_anime(self, aid: Aid, rating: float) -> List[str]:
        '''
        Vote for an anime identified by aid. rating is a number between 1 and 10
        '''
        # VOTE type={int2 type}&id={int4 id}[&value={int4 vote value}&epno={int4 episode number}]
        args: ApiArgs = dict()
        args['id'] = aid
        args['type'] = 1
        args['value'] = int(rating * 100)

        while 1:
            code, text, data = self.execute('VOTE', args)
            if code in (260, 262):
                return data[0]
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    # def get_anime(self, aid=None, aname=None, amask=None, retry=False):
    #     args = {}
    #     if not aid == None:
    #         args['aid'] = aid
    #     elif not aname == None:
    #         args['aname'] == aname
    #     else:
    #         raise TypeError('must set either aid or aname')

    #     args['amask'] = amask or '00'*7

    #     while 1:
    #         code, text, data = self.execute('ANIME', args)
    #         if code == 230:
    #             return data[0]
    #         elif code == 330:
    #             raise AniDBUnknownAnime()
    #         elif code in (501, 506):
    #             self.auth()
    #         else:
    #             raise AniDBReplyError(code, text)

    # def get_animedesc(self, aid):
    #     args = {'aid': aid, 'part': 0}
    #     description = ''
    #     while 1:
    #         code, text, data = self.execute('ANIMEDESC', args)
    #         if code == 233:
    #             curpart, maxpart, desc = data[0]
    #             description += desc
    #             if curpart == maxpart:
    #                 return description
    #             else:
    #                 args['part'] = int(curpart)+1
    #         elif code == 330:
    #             raise AniDBUnknownAnime()
    #         elif code == 333:
    #             raise AnidBUnknownDescription()
    #         elif code in (501, 506):
    #             self.auth()
    #         else:
    #             raise AniDBReplyError(code, text)

    def remove_wishlist(self, aid: Aid) -> None:
        args = {'aid': aid}
        while 1:
            code, text, data = self.execute('WISHLISTDEL', args)
            if code == 227:
                return
            if code == 323:
                raise AniDBNoWishlist()
            elif code == 330:
                raise AniDBUnknownAnime()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def send_raw(self, command: str, info: ApiArgs) -> Tuple[int, str, List[Any]]:
        while 1:
            code, text, data = self.execute(command, info)
            if code in (501, 506):
                self.auth()
            else:
                return (code, text, data)
