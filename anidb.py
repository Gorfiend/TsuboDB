#!/usr/bin/env python3

import pyanidb
import pyanidb.hash

import argparse
import configparser
import getpass
import os
import sys

from collections import deque

# Workaround for input/raw_input
if hasattr(__builtins__, 'raw_input'):
	input = raw_input

# Colors.

red    = lambda x: '\x1b[1;31m' + x + '\x1b[0m'
green  = lambda x: '\x1b[1;32m' + x + '\x1b[0m'
yellow = lambda x: '\x1b[1;33m' + x + '\x1b[0m'
blue   = lambda x: '\x1b[1;34m' + x + '\x1b[0m'

# Config.

config = {}
try:
	cp = configparser.ConfigParser()
	cp.read([os.path.expanduser('~/.pyanidb.conf'), os.path.join('.', 'userData', 'pyanidb.conf')])
	for option in cp.options('pyanidb'):
		config[option] = cp.get('pyanidb', option)
except IOError as e:
	pass

# Options.

parser = argparse.ArgumentParser(description='Manage anidb files/mylist')

parser.add_argument('-u', '--username', help = 'AniDB username.',
	action = 'store', default = config.get('username'))
parser.add_argument('-p', '--password', help = 'AniDB password.',
	action = 'store', default = config.get('password'))

parser.add_argument('-r', '--recursive', help = 'Recurse into directories.',
	action = 'store_true', default = False)
parser.add_argument('-s', '--suffix', help = 'File suffix for recursive matching.',
	action = 'append', default = config.get('suffix', '').split())
parser.add_argument('-c', '--no-cache', help = 'Do not use cached values.',
	action = 'store_false', dest = 'cache', default = int(config.get('cache', '1')))

parser.add_argument('-m', '--multihash', help = 'Calculate additional checksums.',
	action = 'store_true', default = False)
parser.add_argument('-i', '--identify', help = 'Identify files.',
	action = 'store_true', default = False)
parser.add_argument('-a', '--add', help = 'Add files to mylist.',
	action = 'store_true', default = False)
parser.add_argument('-w', '--watched', help = 'Mark files watched.',
	action = 'store_true', default = False)

parser.add_argument('-n', '--rename', help = 'Rename files.',
	action = 'store_true', default = False)
parser.add_argument('-f', '--format', help = 'Filename format.',
	action = 'store', default = config.get('format'))


parser.add_argument('paths', metavar='Path', nargs='+',
	help='path to video to import.')

args = parser.parse_args()

# Defaults.

if args.cache:
	try:
		import xattr
	except ImportError:
		print(red('No xattr, caching disabled.'))
		args.cache = False
args.identify = args.identify or args.rename
args.login = args.add or args.watched or args.identify
if not args.suffix:
	args.suffix = ['avi', 'ogm', 'mkv']
if not args.format:
	args.format = r'_[%group]_%anime_-_%epno%ver_[%CRC].%suf'

if args.login:
	if not args.username:
		args.username = input('Username: ')
	if not args.password:
		args.password = getpass.getpass()

# Input files.

files = []
remaining = deque(args.paths)
while remaining:
	name = remaining.popleft()
	if not os.access(name, os.R_OK):
		print('{0} {1}'.format(red('Invalid file:'), name))
	elif os.path.isfile(name):
		files.append(name)
	elif os.path.isdir(name):
		if not args.recursive:
			print('{0} {1}'.format(red('Is a directory:'), name))
		else:
			for sub in sorted(os.listdir(name)):
				if sub.startswith('.'):
					continue
				sub = os.path.join(name, sub)
				if os.path.isfile(sub) and any(sub.endswith('.' + suffix) for suffix in args.suffix):
					files.append(sub)
				elif os.path.isdir(sub):
					remaining.appendleft(sub)

if not files:
	print(blue('Nothing to do.'))
	sys.exit(0)

# Authorization.

if args.login:
	a = pyanidb.AniDB(args.username, args.password)
	try:
		a.auth()
		print('{0} {1}'.format(blue('Logged in as user:'), args.username))
	except pyanidb.AniDBUserError:
		print(red('Invalid username/password.'))
		sys.exit(1)
	except pyanidb.AniDBTimeout:
		print(red('Connection timed out.'))
		sys.exit(1)
	except pyanidb.AniDBError as e:
		print('{0} {1}'.format(red('Fatal error:'), e))
		sys.exit(1)

# Hashing.

hashed = unknown = 0

for file in pyanidb.hash.hash_files(files, args.cache, (('ed2k', 'md5', 'sha1', 'crc32') if args.multihash else ('ed2k',))):
	print('{0} ed2k://|file|{1}|{2}|{3}|{4}'.format(blue('Hashed:'),  file.name, file.size, file.ed2k, ' (cached)' if file.cached else ''))
	fid = (file.size, file.ed2k)
	hashed += 1
	
	try:
		
		# Multihash.
		if args.multihash:
			print('{0} {1}'.format(blue('MD5:'), file.md5))
			print('{0} {1}'.format(blue('SHA1:'), file.sha1))
			print('{0} {1}'.format(blue('CRC32:'), file.crc32))
		
		# Identify.
		
		if args.identify:
			info = a.get_file(fid, ('gtag', 'kanji', 'epno', 'state', 'epkanji', 'crc32', 'filetype'), True)
			fid = int(info['fid'])
			print('{0} [{1}] {2} - {3} - {4}'.format(green('Identified:'), info['gtag'], info['kanji'], info['epno'], info['epkanji']))
		
		# Renaming.
		
		if args.rename:
			s = args.format
			rename_data = {
				'group': info['gtag'],
				'anime': info['romaji'],
				'epno': info['epno'],
				'ver': {0: '', 4: 'v2', 8: 'v3', 16: 'v4', 32: 'v5'}[(int(info['state']) & 0x3c)],
				'crc': info['crc32'],
				'CRC': info['crc32'].upper(),
				'suf': info['filetype']}
			for name, value in rename_data.items():
				s = s.replace(r'%' + name, value)
			if s[0] == '_':
				s = s[1:].replace(' ', '_')
			s = s.replace('/', '_')
			
			print('{0} {1}'.format(yellow('Renaming to:'), s))
			os.rename(file.name, os.path.join(os.path.split(file.name)[0], s))
		
		# Adding.
		
		if args.add:
			a.add_file(fid, viewed = args.watched, retry = True)
			print(green('Added to mylist.'))
		
		# Watched.
		
		elif args.watched:
			a.add_file(fid, viewed = True, edit = True, retry = True)
			print(green('Marked watched.'))
		
	except pyanidb.AniDBUnknownFile:
		print(red('Unknown file.'))
		unknown += 1
	
	except pyanidb.AniDBNotInMylist:
		print(red('File not in mylist.'))

# Finished.

print(blue('Hashed {0} files{1}.'.format(hashed, ', {0} unknown'.format(unknown) if unknown else '')))
