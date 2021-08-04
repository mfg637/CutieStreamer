import pathlib
import os
import re

import ffmpeg_prober
import imglib
from .. import filesystem
from .. import timecode
from .music_track import MusicTrack
from .tags_list import TagsList
from .gain_constants import REPLAY_GAIN_LEVEL, EBU_R128_GAIN_LEVEL
from customExceptions.audiolib__tagIndexer import CUEparserError, CUEDecodeError

front = re.compile(r"(.*[\W\s]|^)[Ff][Rr][Oo][Nn][Tt]([\W\s].*|$)")
cover = re.compile(r"(.*[^\w]|^)[Cc][Oo][Vv][Ee][Rr]([\W\s].*|$)")
covers_word = re.compile(r"(.*[\W\s]|^)[Cc][Oo][Vv][Ee][Rr][Ss]([\W\s].*|$)")
scans_word = re.compile(r"(.*[\W\s]|^)[Ss][Cc][Aa][Nn][Ss]([\W\s].*|$)")


class MusicTrackBuilder:
	@staticmethod
	def track_file_builder(filename: pathlib.Path):

		_cover_track_num = None
		_start = 0
		f = ffmpeg_prober.probe(filename)
		_fbitrate = int(f['format']["bit_rate"])/1000
		_f = f['format']["format_name"]
		_filename = os.path.realpath(filename)
		_duration = float(f['format']['duration'])
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
			_cover_track_num = video["index"]
		_codec = audio["codec_name"]
		_cdesk = audio["codec_long_name"]
		_sample_rate = int(audio['sample_rate'])
		_bitrate = False
		if "bit_rate" in audio:
			_bitrate = int(audio['bit_rate'])/1000
		else:
			_bitrate = int(f['format']['bit_rate'])/1000
		_channels = int(audio["channels"])
		if "channel_layout" in audio:
			_chandesk = audio["channel_layout"]
		else:
			_chandesk = None
		is_custom_duration = False

		tags = {}

		if 'tags' in f['format']:
			rawtags = f['format']['tags']
			if 'iTunSMPB' in f['format']['tags']:
				is_custom_duration = True
				iTunSMPB = f['format']['tags']['iTunSMPB'].split(' ')
				_duration = int(iTunSMPB[4], 16)/int(audio['sample_rate'])
		elif 'tags' in audio:
			rawtags = audio['tags']
		else:
			rawtags = {}
		for param in rawtags.keys():
			tags[param.lower()] = rawtags[param]

		_taglist = TagsList(tags, str(filename))

		_embeded_cover = bool(video)
		_cover = None
		_raw_cover = None
		if ('tags' in audio) and ('artist' in tags) and ('album' in tags):
			_cover=front_cover_image_picker(
				os.path.dirname(filename),
				artist=tags['artist'],
				album=tags['album']
			)
		else:
			_cover = front_cover_image_picker(os.path.dirname(filename))
		if bool(video):
			_raw_cover = ffmpeg_prober.getPPM_Image(str(filename), index=_cover_track_num)
			_cover = hash(_raw_cover)

		_r128_track_gain = None
		_r128_album_gain = None
		if 'r128_track_gain' in tags:
			_r128_album_gain = _r128_track_gain = \
				EBU_R128_GAIN_LEVEL - int(tags['r128_track_gain']) * (2 ** -8)
		elif 'replaygain_track_gain' in tags:
			_r128_album_gain = _r128_track_gain = \
				REPLAY_GAIN_LEVEL - float(tags['replaygain_track_gain'].split(' ')[0])
		if 'r128_album_gain' in tags:
			_r128_album_gain = EBU_R128_GAIN_LEVEL - int(tags['r128_album_gain']) * (2 ** -8)
		elif 'replaygain_album_gain' in tags:
			_r128_album_gain = \
				REPLAY_GAIN_LEVEL - float(tags['replaygain_album_gain'].split(' ')[0])

		_chapters = []
		if len(f['chapters']) > 1:
			i = 1
			for chapter in f['chapters']:
				chapter_tags = tags.copy()
				for param in chapter['tags'].keys():
					chapter_tags[param.lower()] = chapter['tags'][param]

				chapter_start = 0
				chapter_duration = _duration

				if 'start_time' in chapter:
					chapter_start = float(chapter['start_time'])
					if 'end_time' in chapter:
						chapter_duration = float(chapter['end_time'])-chapter_start

				if 'track' not in chapter_tags:
					chapter_tags['track'] = str(i)
					i += 1

				if 'title' in tags and 'album' not in chapter_tags:
					chapter_tags['album'] = tags['title']
				if 'artist' in tags and 'album_artist' not in chapter_tags:
					chapter_tags['album_artist'] = tags['artist']
				_chapters.append(
					MusicTrack(
						filename=_filename,
						bitrate=_bitrate,
						channels=_channels,
						codec=_codec,
						cdesk=_cdesk,
						sample_rate=_sample_rate,
						chandesk=_chandesk,
						cover=_cover,
						start=chapter_start,
						duration=chapter_duration,
						format_name=_f,
						raw_cover=_raw_cover,
						cover_track_num=_cover_track_num,
						tags=TagsList(chapter_tags, filename),
						track_gain=_r128_track_gain,
						album_gain=_r128_album_gain,
						is_custom_duration=is_custom_duration
					)
				)
			return _chapters
		else:
			return MusicTrack(
				codec=_codec,
				bitrate=_bitrate,
				channels=_channels,
				filename=filename,
				start=_start,
				duration=_duration,
				cover=_cover,
				sample_rate=_sample_rate,
				cdesk=_cdesk,
				chandesk=_chandesk,
				format_name=_f,
				raw_cover=_raw_cover,
				cover_track_num=_cover_track_num,
				tags=_taglist,
				track_gain=_r128_track_gain,
				album_gain=_r128_album_gain
			)

	@staticmethod
	def cue_sheet_indexer(CUEfile: str):
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
						tracks[last_track_id]['artist'] = read_string(line)
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
							'file': file,
							'index': None,
							'duration': None
						}
					)
					last_track_id += 1
				elif line.lstrip().split(' ')[:2] == ["INDEX", "00"]:
					if last_track_id > 0:
						tracks[last_track_id - 1]['duration'] = timecode.CUEparse(line.lstrip().split(' ')[2])
				elif line.lstrip().split(' ')[:2] == ["INDEX", "01"]:
					tracks[last_track_id]['index'] = timecode.CUEparse(line.lstrip().split(' ')[2])
				elif line[:9] == "REM GENRE":
					genre = read_string(line)
				elif line[:8] == "REM DATE":
					date = line[10:]
		except UnicodeDecodeError:
			raise CUEDecodeError(CUEfile)
		general_tags = {
			"album": album,
			"album_artist": album_artist,
			"genre": genre,
			"date": date
		}
		for i in range(len(tracks)):
			duration = None
			if tracks[i]['duration'] is not None:
				duration = tracks[i]['duration'] - tracks[i]['index']
			elif bool(i < last_track_id) and (tracks[i]['file'] == tracks[i + 1]['file']):
				duration = tracks[i + 1]['index'] - tracks[i]['index']
			tracks[i].pop('duration')
			tags = general_tags.copy()
			tags['track'] = tracks[i]['track']
			if tracks[i]['artist']:
				tags['artist'] = tracks[i]['artist']
			if tracks[i]['title']:
				tags['title'] = tracks[i]['title']
			_file = tracks[i]['file']
			#index.append(CUEindex(album, album_artist, genre, date, directory, tracks[i], duration))

			_cover_track_num = None
			_filename = os.path.join(directory, _file)
			f = ffmpeg_prober.probe(_filename)
			_f = f['format']["format_name"]

			_cover = front_cover_image_picker(
				directory,
				artist=tags['artist'],
				album=tags['album']
			)
			_start = tracks[i]['index']
			_duration = duration
			if duration is None:
				_duration = float(f['format']['duration']) - tracks[i]['index']
			audio = False
			video = False
			_raw_cover = None
			for stream in f['streams']:
				if (stream['codec_type'] == "audio") & (not audio):
					audio = stream
				elif (stream['codec_type'] == "video") and \
						((not video) or stream['tags']['comment'] == "Cover (front)"):
					_cover_track_num = stream["index"]
					_raw_cover = ffmpeg_prober.getPPM_Image(_filename, index=_cover_track_num)
					_cover = hash(_raw_cover)
			_codec = audio["codec_name"]
			_cdesk = audio["codec_long_name"]
			if ('tags' in f['format']) and ('encoder' in f['format']['tags']):
				tags['encoder'] = f['format']['tags']['encoder']
			elif ('tags' in audio) and ('encoder' in audio['tags']):
				tags['encoder'] = audio['tags']['encoder']

			_r128_track_gain = None
			_r128_album_gain = None
			if 'R128_TRACK_GAIN' in audio['tags']:
				_r128_album_gain = _r128_track_gain = \
					EBU_R128_GAIN_LEVEL - int(tags['R128_TRACK_GAIN']) * (2 ** -8)
			if 'R128_ALBUM_GAIN' in tags:
				_r128_album_gain = EBU_R128_GAIN_LEVEL - int(tags['R128_ALBUM_GAIN']) * (2 ** -8)

			_sample_rate = int(audio['sample_rate'])
			_bitrate = False
			if "bit_rate" in audio:
				_bitrate = int(audio['bit_rate']) / 1000
			else:
				_bitrate = int(f['format']['bit_rate']) / 1000
			_channels = int(audio["channels"])
			_chandesk = audio["channel_layout"]

			index.append(
					MusicTrack(
						filename=_filename,
						bitrate=_bitrate,
						channels=_channels,
						codec=_codec,
						cdesk=_cdesk,
						sample_rate=_sample_rate,
						chandesk=_chandesk,
						cover=_cover,
						start=_start,
						duration=_duration,
						format_name=_f,
						raw_cover=_raw_cover,
						cover_track_num=_cover_track_num,
						tags=TagsList(tags, _file),
						track_gain=_r128_track_gain,
						album_gain=_r128_album_gain
					)
				)

		return index


def front_cover_image_picker(dir, album=False, artist=False):
	imgext= {'jpg', 'jpeg', 'png', 'tif', 'webp', 'gif'}
	filelist = filesystem.files(dir)
	dirlist = filesystem.directories(pathlib.Path(dir))
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
