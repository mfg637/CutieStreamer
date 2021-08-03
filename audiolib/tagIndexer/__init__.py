#!/usr/bin/python3
# -*- coding: utf-8 -*-


import ffmpeg_prober, imglib, os, platform, re, custom_exceptions
import logging
import pathlib
from customExceptions.audiolib__tagIndexer import CUEparserError, CUEDecodeError
from .music_track import MusicTrack
from .tags_list import TagsList
from .gain_constants import REPLAY_GAIN_LEVEL, EBU_R128_GAIN_LEVEL
from .. import timecode, filesystem

from pathlib import Path
import PIL.Image
import io
import abc

logger = logging.getLogger(__name__)

front = re.compile(r"(.*[\W\s]|^)[Ff][Rr][Oo][Nn][Tt]([\W\s].*|$)")
cover = re.compile(r"(.*[^\w]|^)[Cc][Oo][Vv][Ee][Rr]([\W\s].*|$)")
covers_word = re.compile(r"(.*[\W\s]|^)[Cc][Oo][Vv][Ee][Rr][Ss]([\W\s].*|$)")
scans_word = re.compile(r"(.*[\W\s]|^)[Ss][Cc][Aa][Nn][Ss]([\W\s].*|$)")
num = re.compile(r"\d+")


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
		self._iTunSMPB = data['iTunSMPB']
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


class MusicFile(MusicTrack):
	def __init__(self, filename):

		self._isChapter = False
		self._cover_track_num = None
		self._start = 0
		f = ffmpeg_prober.probe(filename)
		self._fbitrate = int(f['format']["bit_rate"])/1000
		self._f = f['format']["format_name"]
		self._filename = os.path.realpath(filename)
		self._duration = float(f['format']['duration'])
		audio = False
		video = None
		for stream in f['streams']:
			if (stream['codec_type'] == "audio") & (not audio):
				audio = stream
			elif (stream['codec_type'] == "video") & (not video):
				video = stream
			elif stream['codec_type'] == "video" \
				and "comment" in stream['tags'] and \
				stream['tags']['comment'] == "Cover (front)":
					video = stream
		if video is not None:
			self._cover_track_num = video["index"]
		self._codec = audio["codec_name"]
		self._cdesk = audio["codec_long_name"]
		self._sample_rate = int(audio['sample_rate'])
		self._bitrate = False
		if "bit_rate" in audio:
			self._bitrate = int(audio['bit_rate'])/1000
		else:
			self._bitrate = int(f['format']['bit_rate'])/1000
		self._channels = int(audio["channels"])
		if "channel_layout" in audio:
			self._chandesk = audio["channel_layout"]
		else:
			self._chandesk = None
		self._iTunSMPB = False

		tags = {}

		if 'tags' in f['format']:
			rawtags = f['format']['tags']
			if 'iTunSMPB' in f['format']['tags']:
				self._iTunSMPB = True
				iTunSMPB = f['format']['tags']['iTunSMPB'].split(' ')
				self._duration=int(iTunSMPB[4], 16)/int(audio['sample_rate'])
		elif 'tags' in audio:
			rawtags = audio['tags']
		else:
			rawtags = {}
		for param in rawtags.keys():
			tags[param.lower()] = rawtags[param]

		self._taglist = TagsList(tags, filename)

		self._embeded_cover = bool(video)
		if ('tags' in audio) and ('artist' in tags) and ('album' in tags):
			self._cover=front_cover_image_picker(
				os.path.dirname(filename),
				artist=tags['artist'],
				album=tags['album']
			)
		else:
			self._cover = front_cover_image_picker(os.path.dirname(filename))
		if bool(video):
			self._raw_cover = ffmpeg_prober.getPPM_Image(filename, index=self._cover_track_num)
			self._cover = hash(self._raw_cover)
		else:
			self._raw_cover = None
		# TODO: to be removed
		# self._chapters = []
		# if len(f['chapters']) > 1:
		# 	i = 1
		# 	for chapter in f['chapters']:
		# 		tags = dict()
		# 		for param in chapter['tags'].keys():
		# 			tags[param.lower()] = chapter['tags'][param]
		#
		# 		if 'start_time' in chapter:
		# 			start = float(chapter['start_time'])
		# 			if 'end_time' in chapter:
		# 				duration = float(chapter['end_time'])-start
		# 			else:
		# 				duration = self._duration
		# 		else:
		# 			start = 0
		# 			duration = self._duration
		# 		if 'title' not in tags and 'title' in self._tags:
		# 			tags['title'] = self._tags['title']
		# 		if 'artist' not in tags and 'artist' in self._tags:
		# 			tags['artist'] = self._tags['artist']
		# 		if 'track' not in tags:
		# 			tags['track'] = str(i)
		# 			i += 1
		# 		if 'album' in self._tags:
		# 			tags['album'] = self._tags['album']
		# 		elif 'title' in self._tags:
		# 			tags['album'] = self._tags['title']
		# 		if 'album_artist' in self._tags:
		# 			tags['album_artist'] = self._tags['album_artist']
		# 		if 'disc' in self._tags:
		# 			tags['disc'] = self._tags['disc']
		# 		if 'date' in self._tags:
		# 			tags['date'] = self._tags['date']
		# 		if 'genre' in self._tags:
		# 			tags['genre'] = self._tags['genre']
		# 		self._chapters.append(
		# 			MusicTrack(
		# 				filename=self._filename,
		# 				bitrate=self._bitrate,
		# 				channels=self._channels,
		# 				codec=self._codec,
		# 				cdesk=self._cdesk,
		# 				sample_rate=self._sample_rate,
		# 				chandesk=self._chandesk,
		# 				cover=self._cover,
		# 				start=start,
		# 				duration=duration,
		# 				isChapter=True,
		# 				format_name=self._f,
		# 				embeded_cover=self._embeded_cover,
		# 				cover_track_num=self._cover_track_num,
		# 				**tags
		# 			)
		# 		)
		self._r128_track_gain = None
		self._r128_album_gain = None
		if 'r128_track_gain' in tags:
			self._r128_album_gain = self._r128_track_gain = \
				EBU_R128_GAIN_LEVEL - int(tags['r128_track_gain']) * (2 ** -8)
		elif 'replaygain_track_gain' in tags:
			self._r128_album_gain = self._r128_track_gain = \
				REPLAY_GAIN_LEVEL - float(tags['replaygain_track_gain'].split(' ')[0])
		if 'r128_album_gain' in tags:
			self._r128_album_gain = EBU_R128_GAIN_LEVEL - int(tags['r128_album_gain']) * (2 ** -8)
		elif 'replaygain_album_gain' in tags:
			self._r128_album_gain = \
				REPLAY_GAIN_LEVEL - float(tags['replaygain_album_gain'].split(' ')[0])

	def print_metadata(self):
		print(self._filename)
		if self._bitrate:
			print(self._f+" "+self._codec+" "+str(self._bitrate)+"k "+self._chandesk)
		else:
			print(self._f+" "+self._codec+" "+str(self._fbitrate)+"k "+self._chandesk)
		self._taglist.print_metadata()


class CUEindex(MusicTrack):
	def __init__(self, album, album_artist, genre, date, directory, current_track, duration):
		self._isChapter = False
		self._iTunSMPB = False
		self._cover_track_num = None
		filename = os.path.join(directory, current_track['file'])
		f = ffmpeg_prober.probe(filename)
		self._f = f['format']["format_name"]
		tags = {'album': album, 'album_artist': album_artist}
		tags.update(current_track)
		if genre:
			tags['genre'] = genre
		if date:
			tags['date'] = date
		self._cover = front_cover_image_picker(
			directory,
			artist=tags['artist'],
			album=tags['album']
		)
		self._start = current_track['index']
		if duration is not None:
			self._duration = duration
		else:
			self._duration = float(f['format']['duration']) - current_track['index']
		audio = False
		video = False
		self._embeded_cover=False
		self._raw_cover=None
		for stream in f['streams']:
			if (stream['codec_type'] == "audio") & (not audio):
				audio = stream
			elif (stream['codec_type'] == "video") and \
					((not video) or stream['tags']['comment']=="Cover (front)"):
				self._embeded_cover = True
				self._cover_track_num = stream["index"]
				self._raw_cover=ffmpeg_prober.getPPM_Image(filename, index=self._cover_track_num)
				self._cover = hash(self._raw_cover)
		self._codec = audio["codec_name"]
		self._cdesk = audio["codec_long_name"]
		if ('tags' in f['format']) and ('encoder' in f['format']['tags']):
			tags['encoder'] = f['format']['tags']['encoder']
		elif ('tags' in audio) and ('encoder' in audio['tags']):
			tags['encoder'] = audio['tags']['encoder']
		self._sample_rate = int(audio['sample_rate'])
		self._bitrate = False
		if "bit_rate" in audio:
			self._bitrate = int(audio['bit_rate'])/1000
		else:
			self._bitrate = int(f['format']['bit_rate'])/1000
		self._channels = int(audio["channels"])
		self._chandesk = audio["channel_layout"]
		self._filename = filename
		self._taglist = TagsList(tags, filename)
		self._r128_track_gain = None
		self._r128_album_gain = None


def CUEindexer(CUEfile):
	album = ""
	album_artist = ""
	tracks = []
	genre, date = None, None
	directory = os.path.realpath(os.path.dirname(CUEfile))
	last_track_id = -1
	file = ""
	f = open(CUEfile, 'r')
	index = []
	try:
		for line in f:
			if line.lstrip().split(' ')[0] == "PERFORMER":
				if last_track_id == -1:
					album_artist = read_string(line)
				else:
					tracks[last_track_id]['artist']=read_string(line)
			elif line.lstrip().split(' ')[0] == "TITLE":
				if last_track_id == -1:
					album = read_string(line)
				else:
					tracks[last_track_id]['title'] = read_string(line)
			elif line[:4] == "FILE":
				file = read_string(line)
				if os.path.exists(os.path.join(directory, file)):
					if last_track_id > 0 and bool(tracks[last_track_id - 1]['duration']) and \
							(tracks[last_track_id]['index'] is None):
						tracks[last_track_id]['file'] = file
				else:
					raise CUEparserError(line, 'File not exists')
			elif line.lstrip().split(' ')[0] == "TRACK":
				tracks.append(
					{
						'track': line.lstrip().split(' ')[1],
						'artist': '',
						'title': '',
						'index': None,
						'file': file,
						'duration': None
					}
				)
				last_track_id += 1
			elif line.lstrip().split(' ')[:2] == ["INDEX", "00"]:
				if last_track_id > 0:
					tracks[last_track_id-1]['duration'] = timecode.CUEparse(line.lstrip().split(' ')[2])
			elif line.lstrip().split(' ')[:2] == ["INDEX", "01"]:
				tracks[last_track_id]['index'] = timecode.CUEparse(line.lstrip().split(' ')[2])
			elif line[:9] == "REM GENRE":
				genre = read_string(line)
			elif line[:8] == "REM DATE":
				date = line[10:]
	except UnicodeDecodeError:
		raise CUEDecodeError(CUEfile)
	for i in range(len(tracks)):
		duration = None
		if tracks[i]['duration'] is not None:
			duration = tracks[i]['duration'] - tracks[i]['index']
		elif bool(i < last_track_id) and (tracks[i]['file'] == tracks[i + 1]['file']):
			duration = tracks[i + 1]['index'] - tracks[i]['index']
		tracks[i].pop('duration')
		index.append(CUEindex(album, album_artist, genre, date, directory, tracks[i], duration))
	return index


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
			if pathlib.Path(file).suffix.lower() == 'cue':
				index = CUEindexer(file)
				songlist += index
		if bool(songlist):
			return songlist
	except CUEparserError as e:
		print('Error at line:\n{} {}'.format(e.line, e.message))
	except CUEDecodeError as e:
		print('file', e.file, 'can\'t decode as Unicode charset')
	for file in filelist:
		if pathlib.Path(file).suffix.lower() in auext:
			songlist.append(MusicFile(file))
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


def front_cover_image_picker(dir, album=False, artist=False):
	imgext= {'jpg', 'jpeg', 'png', 'tif', 'webp', 'gif'}
	filelist = filesystem.files(dir)
	dirlist = filesystem.directories(Path(dir))
	for subdir in dirlist:
		if covers_word.search(os.path.basename(str(subdir))) is not None or \
				scans_word.search(os.path.basename(str(subdir))) is not None:
			filelist += filesystem.files(os.path.join(dir, str(subdir)))
	imglist=[]
	for file in filelist:
		if (os.path.splitext(os.path.basename(file))[1]).lower()[1:] in imgext:
			imglist.append(file)
	albumart=set(imglist)
	if (bool(album) & bool(artist)):
		album_artist = re.compile(artist+r'[_\s]-[_\s]'+album)
		for img in albumart:
			if album_artist.search(os.path.basename(img)) is not None:
				return os.path.join(dir, img)
	for img in albumart:
		if front.search(os.path.basename(img)) is not None:
			return img
		elif cover.search(os.path.basename(img)) is not None:
			return img
		elif 'folder.jpg' in img:
			return img
	try:
		founded_image = imglib.get_max_resolution_image(imglist)
	except KeyError:
		print("not found front cover in "+dir)
	else:
		if founded_image:
			return founded_image
		else:
			return False


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
			playlist.append(MusicFile(os.path.normpath(os.path.join(playlist_dir, line))))
	return playlist
