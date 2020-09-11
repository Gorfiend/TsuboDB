import socket
import time

from tsubodb.types import *

protover = 3
client = 'tsubodb'
clientver = 2

states = {
    'unknown': 0,
    'hdd': 1,
    'cd': 2,
    'deleted': 3,
    'shared': 4,
    'release': 5}


fmask = [
    '', 'aid', 'eid', 'gid', 'lid', 'otherepisodes', 'deprecated', 'state',
    'size', 'ed2k', 'md5', 'sha1', 'crc32', '', 'vidcolordep', '',
    'quality', 'source', 'acodec', 'abitrate', 'vcodec', 'vbitrate', 'vres', 'filetype',
    'dublang', 'sublang', 'length', 'description', 'aireddate', '', '', 'anidbfilename',
    'mstate', 'mfilestate', 'mviewed', 'mviewdate', 'mstorage', 'msource', 'mother', '']
    # Note: the m* mylist infos don't seem to work (return blanks always)

amask = [
    'eptotal', 'eplast', 'year', 'type', 'relaidlsit', 'reladitype', 'categorylist', '',
    'romaji', 'kanji', 'english', 'other', 'shortname', 'synonyms', '', '',
    'epno', 'epname', 'epromaji', 'epkanji', 'eprating', 'epvotecount', '', '',
    'groupname', 'groupshortname', 'category', '', '', '', '', 'dateaidupdated']


joined_masks = fmask + amask
joined_masks.reverse()
masks = dict([(joined_masks[i], 1 << i) for i in range(len(joined_masks)) if joined_masks[i]])

class AniDB:
    def __init__(self, username: str, password: str, localport: int = 1234, server=('api.anidb.info', 9000)):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', localport))
        self.sock.settimeout(10)
        self.username = username
        self.password = password
        self.server = server
        self.session = ''
        self.lasttime = 0

    def __del__(self):
        self.logout()
        self.sock.close()

    def newver_msg(self):
        print('New version available.')

    def retry_msg(self):
        print('Connection timed out, retrying.')

    def execute(self, cmd, args=None, retry=False):
        if not args:
            args = {}
        if cmd not in ('PING', 'ENCRYPT', 'ENCODING', 'AUTH', 'VERSION'):
            if not self.session:
                self.auth()
            args['s'] = self.session
        while 1:
            params = '&'.join(['{0}={1}'.format(*a) for a in args.items()])
            data = f'{cmd} {params}\n'
            if 'pass' in args:
                paramsCen = params.replace(args['pass'], 'PASSWORD')
            else:
                paramsCen = params
            print('>', cmd, paramsCen)
            t = time.time()
            if t < self.lasttime + 2:
                time.sleep(self.lasttime + 2 - t)
            self.lasttime = time.time()
            self.sock.sendto(data.encode(), 0, self.server)
            try:
                data = self.sock.recv(8192).decode().split('\n')
                print('<', data)
            except socket.timeout:
                if retry:
                    self.retry_msg()
                else:
                    raise AniDBTimeout()
            else:
                break
        code, text = data[0].split(' ', 1)
        data = [line.split('|') for line in data[1:-1]]
        code = int(code)
        return code, text, data

    def ping(self):
        t = time.time()
        try:
            return self.execute('PING')[0] == 300 and time.time() - t or None
        except AniDBTimeout:
            return None

    def auth(self):
        code, text, data = self.execute('AUTH', {'user': self.username, 'pass': self.password, 'protover': protover,
                                                 'client': client, 'clientver': clientver, 'enc': 'utf8'})
        if code in (200, 201):
            self.session = text.split(' ', 1)[0]
            if code == 201:
                self.newver_msg()
        elif code == 500:
            raise AniDBUserError()
        else:
            raise AniDBReplyError(code, text)

    def logout(self):
        if self.session:
            try:
                self.execute('LOGOUT', {'s': self.session})
                self.session = ''
            except AniDBError:
                pass

    def get_file(self, file: LocalFileInfo, info_codes, retry=False):
        args: dict
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
            code, text, data = self.execute('FILE', args, retry)
            if code == 220:
                return dict([(name, data[0].pop(0)) for name in ['fid'] + info_codes])
            elif code == 320:
                raise AniDBUnknownFile()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def get_mylist(self, fid: Fid, retry=False):
        args = {'fid': fid}
        while 1:
            code, text, data = self.execute('MYLIST', args, retry)
            if code == 221:
                return data[0]
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def get_mylist_lid(self, lid: Lid, retry=False):
        args = {'lid': lid}
        while 1:
            code, text, data = self.execute('MYLIST', args, retry)
            if code == 221:
                return data[0]
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def add_file(self, fid: Fid, state=None, viewed=False, source=None, storage=None, other=None, edit=False, retry=False):
        args: dict = {'fid': fid}
        if not edit and state == None:
            state = 'hdd'
        if state != None:
            args['state'] = states[state]
        if viewed != None:
            args['viewed'] = int(bool(viewed))
        if source != None:
            args['source'] = source
        if storage != None:
            args['storage'] = storage
        if other != None:
            args['other'] = other
        if edit:
            args['edit'] = 1
        while 1:
            code, text, data = self.execute('MYLISTADD', args, retry)
            if code in (210, 310, 311):
                return code, data[0]
            elif code == 320:
                raise AniDBUnknownFile()
            elif code == 411:
                raise AniDBNotInMylist()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def mark_watched(self, lid: Lid):
        args: dict = {'lid': lid}
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

    def rate_anime(self, aid: Aid, rating: float, retry=False):
        '''
        Vote for an anime identified by aid. rating is a number between 1 and 10
        '''
        # VOTE type={int2 type}&id={int4 id}[&value={int4 vote value}&epno={int4 episode number}]
        args: dict = dict()
        args['id'] = aid
        args['type'] = 1
        args['value'] = int(rating * 100)

        while 1:
            code, text, data = self.execute('VOTE', args, retry)
            if code in (260, 262):
                return data[0]
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def get_anime(self, aid=None, aname=None, amask=None, retry=False):
        args = {}
        if not aid == None:
            args['aid'] = aid
        elif not aname == None:
            args['aname'] == aname
        else:
            raise TypeError('must set either aid or aname')

        args['amask'] = amask or '00'*7

        while 1:
            code, text, data = self.execute('ANIME', args, retry)
            if code == 230:
                return data[0]
            elif code == 330:
                raise AniDBUnknownAnime()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def get_animedesc(self, aid, retry=False):
        args = {'aid': aid, 'part': 0}
        description = ''
        while 1:
            code, text, data = self.execute('ANIMEDESC', args, retry)
            if code == 233:
                curpart, maxpart, desc = data[0]
                description += desc
                if curpart == maxpart:
                    return description
                else:
                    args['part'] = int(curpart)+1
            elif code == 330:
                raise AniDBUnknownAnime()
            elif code == 333:
                raise AnidBUnknownDescription()
            elif code in (501, 506):
                self.auth()
            else:
                raise AniDBReplyError(code, text)

    def remove_wishlist(self, aid: Aid, retry=False):
        args = {'aid': aid}
        while 1:
            code, text, data = self.execute('WISHLISTDEL', args, retry)
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

    def send_raw(self, command: str, info: dict, retry=False):
        while 1:
            code, text, data = self.execute(command, info, retry)
            if code in (501, 506):
                self.auth()
            else:
                return (code, text, data)
