#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging

import ffmpeg_prober, imglib, os, platform, re, custom_exceptions
from . import timecode, filesystem
from .enums import GainModeEnum
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

EBU_R128_GAIN_LEVEL = -23
REPLAY_GAIN_LEVEL = -18


class CUEparserError(Exception):
	def __init__(self, line, message):
		self.line = line
		self.message = message


class CUEDecodeError(Exception):
	def __init__(self, file):
		self.file = file


def decodeTags(text:str, from_charset, to_charset):
	bintext = text.encode(from_charset)
	return bintext.decode(to_charset)


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


class MusicTrack:
	_tag_param = ['artist', 'title', 'track', 'genre', 'album', 'album_artist', 'date', 'publisher', 'disc']
	_important_tags = ['title', 'track', 'album', 'album_artist']

	def __init__(self, *, codec=None, bitrate=None, channels=None,
					filename=None, start=None,
					duration=None, cover=None, sample_rate=None, cdesk=None,
					chandesk=None, isChapter=False, format_name=None,
					embeded_cover=False, cover_track_num=None, **tags):
		self._sample_rate = sample_rate
		self._tags = {}
		self._start = start
		self._duration = duration
		self._codec = codec
		self._cdesk = cdesk
		self._bitrate = bitrate
		self._channels = channels
		self._chandesk = chandesk
		self._iTunSMPB = False
		self._filename = filename
		self._f = format_name
		self._embeded_cover = embeded_cover
		self._chapters = []
		self._cover_track_num = cover_track_num
		self._tags.update(tags)
		self._cover = cover
		self._isChapter = isChapter
		self._r128_track_gain = None
		self._r128_album_gain = None

	def __getItem(self, FF_num):
		if type(FF_num) is str:
			return FF_num.split('/')[0]
		else:
			return str(FF_num)

	def ffmetamarkup(self):
		ffmetadata=';FFMETADATA1'
		for param in self._tag_param:
			if param in self._tags:
				ffmetadata += "\n{}={}".format(param, self._tags[param])
		return ffmetadata

	def codec(self):
		return self._codec

	def bitrate(self):
		if self._bitrate:
			return self._bitrate
		else:
			return 0

	def channels(self):
		return self._channels

	def title(self):
		if 'title' in self._tags:
			return self._tags['title']
		else:
			return os.path.splitext(os.path.basename(self._filename))[0]

	def getTitle(self):
		if 'title' in self._tags:
			return self._tags['title']
		else:
			return None

	def artist(self):
		if 'artist' in self._tags:
			return self._tags['artist']
		else:
			return "unknown artist"

	def getArtist(self):
		if 'artist' in self._tags:
			return self._tags['artist']
		else:
			return None

	def track(self):
		if 'track' in self._tags:
			track=self.__getItem(self._tags['track'])
			if len(track)<2:
				return '0'+str(track)
			else:
				return str(track)
		else:
			return "00"

	def getTrack(self):
		if 'track' in self._tags:
			return str(self.__getItem(self._tags['track']))
		else:
			return None

	def genre(self):
		if 'genre' in self._tags:
			return self._tags['genre']
		else:
			return None

	def album(self):
		if 'album' in self._tags:
			return self._tags['album']
		else:
			return "untitled"

	def getAlbum(self):
		if 'album' in self._tags:
			return self._tags['album']
		else:
			return None

	def setAlbum(self, value):
		self._tags['album'] = value

	def album_artist(self):
		if 'album_artist' in self._tags:
			return self._tags['album_artist']
		else:
			return "unknown"

	def getAlbumArtist(self):
		if 'album_artist' in self._tags:
			return self._tags['album_artist']
		else:
			return None

	def setAlbumArtist(self, value):
		self._tags['album_artist']=value

	def date(self):
		if 'date' in self._tags:
			return self._tags['date']
		else:
			return None

	def tags(self):
		return self._tags

	def disc(self):
		if 'disc' in self._tags:
			return self.__getItem(self._tags['disc'])
		else:
			return None

	def set_disc(self, value):
		self._tags['disc'] = value

	def start(self):
		return self._start

	def duration(self):
		return self._duration

	def iTunSMPB(self):
		return self._iTunSMPB

	def cover(self):
		if self._cover:
			return self._cover
		else:
			return ''

	def hasEmbededCover(self):
		return self._embeded_cover

	def encoder(self):
		if 'encoder' in self._tags:
			return self._tags['encoder']
		else:
			return ''

	def sample_rate(self):
		return self._sample_rate

	def getChapter(self, id=None):
		if id is None:
			return len(self._chapters)
		else:
			return self._chapters[id]

	def filename(self):
		return self._filename

	def isChapter(self):
		return self._isChapter

	def container(self):
		return self._f

	def serialize(self, playlist_dir):
		cover_replace = False
		if platform.system() == 'Windows':
			filename = os.path.relpath(self._filename, start=playlist_dir)
			if not os.path.isabs(filename):
				cover_replace = True
				filename = re.sub('\\\\', '/', filename)
		else:
			filename = os.path.relpath(self._filename, start=playlist_dir)
		if type(self._cover) is int:
			cover = self._cover
		elif type(self._cover) is str:
			cover = os.path.relpath(self._cover, start=playlist_dir)
			if cover_replace:
				cover = re.sub('\\\\', '/', cover)
		else:
			cover = ''
		return {'tags': self._tags, 'start': self._start, 'duration': self._duration,
				'codec': self._codec, 'cdesk': self._cdesk, 'bitrate': self._bitrate,
				'channels': self._channels, 'chandesk': self._chandesk,
				'iTunSMPB': self._iTunSMPB, 'filename': filename,
				'cover': cover, 'isChapter': self._isChapter,
				'embeded cover': self._embeded_cover, 'sample rate': self._sample_rate,
				'container': self._f, 'cover track index': self._cover_track_num,
				'r128_track_gain': self._r128_track_gain,
				'r128_album_gain': self._r128_album_gain}

	def getRawCover(self):
		return None

	def track_num(self):
		if 'track' in self._tags:
			regex_match = num.match(self._tags['track'])
			logger.debug("track num = %s", regex_match)
			if regex_match is not  None:
				return int(regex_match[0])

	def disc_num(self):
		if 'disc' in self._tags:
			regex_match = num.match(self._tags['disc'])
			logger.debug("disc num = %s", regex_match)
			if regex_match is not None:
				return int(regex_match[0])

	def getCoverIndex(self):
		return self._cover_track_num

	def decode(self):
		for key in self._tags.keys():
			if type(self._tags[key]) is str:
				self._tags[key] = decodeTags(self._tags[key], 'cp1252', 'cp1251')

	def get_front_cover_image(self, size:tuple, force=False):
		if self._embeded_cover:
			imgBuffer = io.BytesIO(
				ffmpeg_prober.getPPM_Image(
					self._filename,
					size='{}x{}'.format(*size),
					force=force,
					index=self._cover_track_num
				)
			)
			return PIL.Image.open(imgBuffer)
		elif self._cover:
			img = PIL.Image.open(self._cover)
			if img.size[0] / img.size[1] > 1.75:
				img = img.crop((img.size[0] - img.size[1], 0, img.size[0], img.size[1]))
			if force:
				return img.resize(size, PIL.Image.LANCZOS)
			else:
				return img.resize(
						imglib.resize(
						img.size[0],
						img.size[1],
						width=size[0],
						height=size[1]
					), PIL.Image.LANCZOS)
		else:
			return None

	def set_r128_track_gain(self, r128_track):
		self._r128_track_gain = r128_track

	def get_r128_track_level(self):
		return self._r128_track_gain

	def get_replay_gain_track_level(self):
		if self._r128_track_gain is not None:
			return self._r128_track_gain + 5

	def _gain(self, current_level, target_level):
		return target_level - current_level

	def r128_track_gain(self):
		target_volume_dbFS = EBU_R128_GAIN_LEVEL
		if self._r128_track_gain is not None:
			return self._gain(self._r128_track_gain, target_volume_dbFS)

	def replay_gain_track(self):
		target_volume_dbFS = REPLAY_GAIN_LEVEL
		if self._r128_track_gain is not None:
			return self._gain(self._r128_track_gain, target_volume_dbFS)

	def set_r128_album_gain(self, r128_album):
		self._r128_album_gain = r128_album

	def get_r128_album_gain(self):
		return self._r128_album_gain

	def get_replay_gain_album(self):
		if self._r128_album_gain is not None:
			return self._r128_album_gain + 5

	def r128_album_gain(self):
		target_volume_dbFS = EBU_R128_GAIN_LEVEL
		if self._r128_album_gain is not None:
			return self._gain(self._r128_album_gain, target_volume_dbFS)
		else:
			return self.r128_track_gain()

	def replay_gain_album(self):
		target_volume_dbFS = REPLAY_GAIN_LEVEL
		if self._r128_album_gain is not None:
			return self._gain(self._r128_album_gain, target_volume_dbFS)
		else:
			return self.replay_gain_track()

	def get_gains(self):
		return {
			GainModeEnum.NONE: None,
			GainModeEnum.R128_GAIN_ALBUM: self.r128_album_gain(),
			GainModeEnum.R128_GAIN_TRACK: self.r128_track_gain(),
			GainModeEnum.REPLAY_GAIN_ALBUM: self.replay_gain_album(),
			GainModeEnum.REPLAY_GAIN_TRACK: self.replay_gain_track()
		}


class DeserializeMusicTrack(MusicTrack):
	def __init__(self, data:dict, playlist_dir):
		self._tags = data['tags']
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


class RawCoverContainMusicTrack(MusicTrack):
	__metaclass__ = abc.ABCMeta

	@abc.abstractmethod
	def __init__(self):
		pass

	def getRawCover(self):
		return self._raw_cover

	def get_front_cover_image(self, size:tuple, force=False):
		if self._embeded_cover and self._raw_cover is not None:
			img = PIL.Image.open(io.BytesIO(self._raw_cover))
			if force:
				return img.resize(size, PIL.Image.LANCZOS)
			else:
				return img.resize(
						imglib.resize(
							img.size[0],
							img.size[1],
							width=size[0],
							height=size[1]
					), PIL.Image.LANCZOS
				)
		else:
			return MusicTrack.get_front_cover_image(self, size, force)


class MusicFile(RawCoverContainMusicTrack):
	def __init__(self, filename):

		self._isChapter = False
		self._tags = {}
		self._cover_track_num = None
		self._start = 0
		f = ffmpeg_prober.probe(filename)
		self._fbitrate = int(f['format']["bit_rate"])/1000
		self._f = f['format']["format_name"]
		self._filename = os.path.realpath(filename)
		self._duration = float(f['format']['duration'])
		audio = False
		video = False
		for stream in f['streams']:
			if (stream['codec_type'] == "audio") & (not audio):
				audio = stream
			elif (stream['codec_type'] == "video") & (not video):
				video = stream
			elif stream['codec_type'] == "video" \
				and "comment" in stream['tags'] and \
				stream['tags']['comment'] == "Cover (front)":
					video = stream
		if video:
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
			self._tags[param.lower()]=rawtags[param]
		self._embeded_cover = bool(video)
		if ('tags' in audio) and ('artist' in self._tags) and ('album' in self._tags):
			self._cover=frontPicker(os.path.dirname(filename),
				artist=self._tags['artist'],
				album=self._tags['album'])
		else:
			self._cover = frontPicker(os.path.dirname(filename))
		if  bool(video):
			self._raw_cover = ffmpeg_prober.getPPM_Image(filename, index=self._cover_track_num)
			self._cover = hash(self._raw_cover)
		else:
			self._raw_cover = None
		self._chapters = []
		if len(f['chapters']) > 1:
			i = 1
			for chapter in f['chapters']:
				tags = dict()
				for param in chapter['tags'].keys():
					tags[param.lower()] = chapter['tags'][param]

				if 'start_time' in chapter:
					start = float(chapter['start_time'])
					if 'end_time' in chapter:
						duration = float(chapter['end_time'])-start
					else:
						duration = self._duration
				else:
					start = 0
					duration = self._duration
				if 'title' not in tags and 'title' in self._tags:
					tags['title'] = self._tags['title']
				if 'artist' not in tags and 'artist' in self._tags:
					tags['artist'] = self._tags['artist']
				if 'track' not in tags:
					tags['track'] = str(i)
					i += 1
				if 'album' in self._tags:
					tags['album'] = self._tags['album']
				elif 'title' in self._tags:
					tags['album'] = self._tags['title']
				if 'album_artist' in self._tags:
					tags['album_artist'] = self._tags['album_artist']
				if 'disc' in self._tags:
					tags['disc'] = self._tags['disc']
				if 'date' in self._tags:
					tags['date'] = self._tags['date']
				if 'genre' in self._tags:
					tags['genre'] = self._tags['genre']
				self._chapters.append(
					MusicTrack(
						filename=self._filename,
						bitrate=self._bitrate,
						channels=self._channels,
						codec=self._codec,
						cdesk=self._cdesk,
						sample_rate=self._sample_rate,
						chandesk=self._chandesk,
						cover=self._cover,
						start=start,
						duration=duration,
						isChapter=True,
						format_name=self._f,
						embeded_cover=self._embeded_cover,
						cover_track_num=self._cover_track_num,
						**tags
					)
				)
		self._r128_track_gain = None
		self._r128_album_gain = None
		if 'r128_track_gain' in self._tags:
			self._r128_album_gain = self._r128_track_gain = \
				EBU_R128_GAIN_LEVEL - int(self._tags['r128_track_gain']) * (2 ** -8)
		elif 'replaygain_track_gain' in self._tags:
			self._r128_album_gain = self._r128_track_gain = \
				REPLAY_GAIN_LEVEL - float(self._tags['replaygain_track_gain'].split(' ')[0])
		if 'r128_album_gain' in self._tags:
			self._r128_album_gain = EBU_R128_GAIN_LEVEL - int(self._tags['r128_album_gain']) * (2 ** -8)
		elif 'replaygain_album_gain' in self._tags:
			self._r128_album_gain = \
				REPLAY_GAIN_LEVEL - float(self._tags['replaygain_album_gain'].split(' ')[0])

	def print_metadata(self):
		print(self._filename)
		if self._bitrate:
			print(self._f+" "+self._codec+" "+str(self._bitrate)+"k "+self._chandesk)
		else:
			print(self._f+" "+self._codec+" "+str(self._fbitrate)+"k "+self._chandesk)
		for param in self._tag_param:
			if param in self._tags:
				print(param+": "+self._tags[param])


class CUEindex(RawCoverContainMusicTrack):
	def __init__(self, album, album_artist, genre, date, directory, current_track, duration):
		self._isChapter = False
		self._iTunSMPB = False
		self._cover_track_num = None
		filename = os.path.join(directory, current_track['file'])
		f = ffmpeg_prober.probe(filename)
		self._f = f['format']["format_name"]
		self._tags = {'album': album, 'album_artist': album_artist}
		self._tags.update(current_track)
		if genre:
			self._tags['genre'] = genre
		if date:
			self._tags['date'] = date
		self._cover = frontPicker(directory,
			artist = self._tags['artist'],
			album = self._tags['album'])
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
			self._tags['encoder'] = f['format']['tags']['encoder']
		elif ('tags' in audio) and ('encoder' in audio['tags']):
			self._tags['encoder'] = audio['tags']['encoder']
		self._sample_rate = int(audio['sample_rate'])
		self._bitrate = False
		if "bit_rate" in audio:
			self._bitrate = int(audio['bit_rate'])/1000
		else:
			self._bitrate = int(f['format']['bit_rate'])/1000
		self._channels = int(audio["channels"])
		self._chandesk = audio["channel_layout"]
		self._filename = filename
		self._chapters = []
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


auext= {'wav', 'mp3', 'm4a', 'flac', 'ogg', 'opus', 'ape', 'tak', 'tta', 'wv', 'mka'}


def sortSongsInAlbum(song):
	if song.disc_num() is not None and song.getTrack() is not None:
		return (song.disc_num() - 1) * 100 + song.track_num()
	elif song.getTrack():
		return song.track_num()
	else:
		return 0


def indexer(dir):
	if platform.system()=="Windows":
		separator = '\\'
	else:
		separator='/'

	filelist=filesystem.files(dir)
	aufile=0
	songlist=[]
	try:
		for file in filelist:
			if os.path.splitext(os.path.basename(file))[1].lower()[1:]=='cue':
				index=CUEindexer(file)
				songlist += index
		if bool(songlist):
			return songlist
	except CUEparserError as e:
		print('Error at line:\n{} {}'.format(e.line, e.message))
	except CUEDecodeError as e:
		print('file', e.file, 'can\'t decode as Unicode charset')
	for file in filelist:
		if (os.path.splitext(os.path.basename(file))[1]).lower()[1:] in auext:
			aufile=MusicFile(file)
			if aufile.getChapter():
				for i in range(aufile.getChapter()):
					songlist.append(aufile.getChapter(i))
			else:
				songlist.append(aufile)
	songlist.sort(key=sortSongsInAlbum)
	listdir=filesystem.directories(Path(dir))
	for directory in listdir:
		songlist+=indexer(str(directory))
	return songlist


def non_recursive_indexer(dir):
	filelist=filesystem.files(str(dir))
	aufile=0
	songlist=[]
	try:
		for file in filelist:
			if os.path.splitext(file)[1].lower()[1:]=='cue':
				index=CUEindexer(os.path.join(str(dir), file))
				songlist+=index
		if bool(songlist):
			return songlist
	except CUEparserError as e:
		print('Error at line:\n{} {}'.format(e.line, e.message))
	except CUEDecodeError as e:
		print('file', e.file, 'can\'t decode as Unicode charset')
	for file in filelist:
		if (os.path.splitext(file)[1]).lower()[1:] in auext:
			aufile=MusicFile(os.path.join(str(dir), file))
			if aufile.getChapter():
				for i in range(aufile.getChapter()):
					songlist.append(aufile.getChapter(i))
			else:
				songlist.append(aufile)
	songlist.sort(key=sortSongsInAlbum)
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
	return songlist


def frontPicker(dir, album=False, artist=False):
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
