#!/usr/bin/python3
# -*- coding: utf-8 -*-


import os, platform, re, custom_exceptions
import logging
import pathlib
from customExceptions.audiolib__tagIndexer import CUEparserError, CUEDecodeError
from . import builders
from .music_track import MusicTrack
from .tags_list import TagsList
from .gain_constants import REPLAY_GAIN_LEVEL, EBU_R128_GAIN_LEVEL
from .. import filesystem

from pathlib import Path

logger = logging.getLogger(__name__)


def read_string(line):
	start_quotes = 0
	end_quotes = 0
	for i in range(len(line)):
		if line[i] == '"':
			if start_quotes:
				end_quotes = i
			else:
				start_quotes = i
	return line[start_quotes+1:end_quotes]


class DeserializeMusicTrack(MusicTrack):
	def __init__(self, data:dict, playlist_dir):
		self._start = data['start']
		self._duration = data['duration']
		self._codec = data['codec']
		self._cdesk = data['cdesk']
		self._bitrate = data['bitrate']
		self._channels = data['channels']
		self._chandesk = data['chandesk']
		self._r128_track_gain = data['r128_track_gain']
		self._r128_album_gain = data['r128_album_gain']
		filename = os.path.normpath(os.path.join(playlist_dir, data['filename']))
		if platform.system() == 'Windows':
			self._filename = re.sub('/', r'\\', filename)
		else:
			self._filename = filename
		self._taglist = TagsList(data['tags'], self._filename)
		self._embeded_cover = data['embeded cover']
		if type(data['cover']) is int:
			self._cover = data['cover']
		elif (type(data['cover']) is str) and len(data['cover']):
			cover = os.path.normpath(os.path.join(playlist_dir, data['cover']))
			if platform.system() == 'Windows':
				self._cover = re.sub('/', r'\\', cover)
			else:
				self._cover = cover
		elif type(data['cover']) is str:
			self._cover=''
		self._isChapter = data['isChapter']
		self._sample_rate = data['sample rate']
		self._f = data['container']
		if "cover track index" in data:
			self._cover_track_num = data["cover track index"]
		else:
			self._cover_track_num = None


auext= {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.ape', '.tak', '.tta', '.wv', '.mka'}


def sortSongsInAlbum(song:MusicTrack):
	tags = song.get_tags_list()
	if tags.disc_num() is not None and tags.getTrack() is not None:
		return (tags.disc_num() - 1) * 100 + tags.track_num()
	elif tags.getTrack():
		return tags.track_num()
	else:
		return 0


def sort_songlist(songlist: list) -> list:
	grouped_songlist = dict()

	for song in songlist:
		tags = song.get_tags_list()
		key = (tags.album_artist(), tags.album())
		try:
			grouped_songlist[key].append(song)
		except KeyError:
			grouped_songlist[key] = list()
			grouped_songlist[key].append(song)
	for key in grouped_songlist.keys():
		grouped_songlist[key].sort(key=sortSongsInAlbum)
	keysort = list(grouped_songlist.keys())
	keysort.sort()
	songlist_result = list()
	for key in keysort:
		songlist_result.extend(grouped_songlist[key])
	return songlist_result


def indexer(dir):
	songlist = fs_musicfiles_scanner(pathlib.Path(dir))
	songlist = sort_songlist(songlist)
	return songlist


def non_recursive_indexer(root):
	filelist = filesystem.files_p(root)
	songlist=[]
	try:
		for file in filelist:
			if pathlib.Path(file).suffix.lower() == '.cue':
				index = builders.MusicTrackBuilder.cue_sheet_indexer(str(file))
				songlist.extend(index)
		if bool(songlist):
			return songlist
	except CUEparserError as e:
		print('Error at line:\n{} {}'.format(e.line, e.message))
	except CUEDecodeError as e:
		print('file', e.file, 'can\'t decode as Unicode charset')
	for file in filelist:
		if pathlib.Path(file).suffix.lower() in auext:
			music_tracks = builders.MusicTrackBuilder.track_file_builder(file)
			if type(music_tracks) == MusicTrack:
				songlist.append(music_tracks)
			elif type(music_tracks) == list:
				songlist.extend(music_tracks)
			else:
				raise TypeError(music_tracks)
	return songlist


def fs_musicfiles_scanner(root:pathlib.Path)->list:
	songlist = non_recursive_indexer(root)
	listdir = filesystem.directories(root)
	for directory in listdir:
		songlist += indexer(str(directory))
	return songlist


def folder_indexer(dir, progressbar):
	listdir = filesystem.directories_tree(Path(dir))
	listdir.insert(0, Path(dir))
	progressbar['maximum'] = len(listdir)+1
	songlist = []
	for directory in listdir:
		songlist += non_recursive_indexer(directory)
		progressbar.step()
		progressbar.update_idletasks()
	songlist = sort_songlist(songlist)
	return songlist


def m3u_indexer(filepath, unicode=False):
	playlist_dir=os.path.dirname(filepath)
	try:
		if unicode:
			file = open(filepath, 'r')
		else:
			file = open(filepath, 'r', encoding='windows-1251')
	except UnicodeEncodeError:
		raise custom_exceptions.invalidFilename(filepath)
	playlist=[]
	f = file.read().splitlines()
	for line in f:
		if (re.match(r'[a-zA-Z0-9а-яА-Я]', line) is not None) and line[0]!='#':
			music_track_filepath = pathlib.Path(os.path.normpath(os.path.join(playlist_dir, line)))
			music_tracks = builders.MusicTrackBuilder.track_file_builder(music_track_filepath)
			if type(music_tracks) == MusicTrack:
				playlist.append(music_tracks)
			elif type(music_tracks) == list:
				playlist.extend(music_tracks)
			else:
				raise TypeError(music_tracks)
	return playlist
