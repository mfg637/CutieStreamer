#!/usr/bin/python3
# -*- coding: utf-8 -*-
# playlist by mfg637

import io
import json
import os
import subprocess
import sys
import zlib
from platform import system
import enum

from PIL import Image

from audiolib.tagIndexer import MusicFile, CUEindexer, DeserializeMusicTrack, m3u_indexer
from . import player, playlist_file_format

if system() == 'Windows':
	status_info = subprocess.STARTUPINFO()
	status_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW


class EndOfPlaylistException(Exception):
	def __init__(self):
		pass


class PlaybackModeEnum(enum.Enum):
	GAPLESS = enum.auto()
	CROSSFADE = enum.auto()


class GainModeEnum(enum.Enum):
	NONE = 0
	REPLAY_GAIN = 1


buf_len = None


class Playlist:
	"""Class describes playlist and is a wrapper for player.
		Only one instance can be displayed in gui."""
	def __init__(self, files, progressbar=None):
		self.tags = []
		if type(files[0]) is str:
			for file in files:
				if os.path.splitext(file)[1] == '.cue':
					self.tags += CUEindexer(file)
				elif os.path.splitext(file)[1] == '.m3u':
					self.tags += m3u_indexer(file)
				elif os.path.splitext(file)[1] == '.m3u8':
					self.tags += m3u_indexer(file, unicode=True)
				else:
					file_index = MusicFile(file)
					if file_index.getChapter():
						for i in range(file_index.getChapter()):
							self.tags.append(file_index.getChapter(i))
					else:
						self.tags.append(file_index)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tags = files
		self._my_player = None
		self._start_offset = 0
		self._timestamp = []
		self._track_number = 0
		self.fading_duration = 10
		self.playback_mode = PlaybackModeEnum.GAPLESS
		self._gain_mode = GainModeEnum.NONE
		self._gui = None
		self._playlist_len = len(self.tags)

	def set_gui(self, link):
		"""Bind GUI class for this playlist"""
		self._gui = link

	def play_from_item(self, item: int):
		if self._my_player is not None:
			self._my_player.clear()
			del self._my_player
		self._track_number = item
		self._start_offset = 0
		self._count_timestamps()
		self.__request_optimizer(item)
		self._my_player.play()

	def play(self):
		if (self._my_player is None) or (self._my_player.is_end()):
			self.__request_optimizer(0)
			self._start_offset = 0
			self._track_number = 0
			self._count_timestamps()
		self._my_player.play()

	def pause(self):
		self._my_player.pause()

	def state(self):
		if self._my_player is None:
			return False
		else:
			return self._my_player.playing

	def stop(self):
		self._my_player.clear()
		del self._my_player
		self._my_player = None

	def clear(self):
		if self._my_player is not None:
			self._my_player.clear()
			del self._my_player
			self._my_player = None

	def _count_timestamps(self):
		self._timestamp = [self.tags[self._track_number].duration() - self._start_offset]
		if self.playback_mode == PlaybackModeEnum.GAPLESS:
			for i in range(self._track_number + 1, len(self.tags)):
				self._timestamp.append(self._timestamp[-1] + self.tags[i].duration())
		elif self.playback_mode == PlaybackModeEnum.CROSSFADE:
			self._timestamp[0] -= self.fading_duration/2
			for i in range(self._track_number + 1, len(self.tags)):
				if i < (len(self.tags)-1):
					self._timestamp.append(self._timestamp[-1] + self.tags[i].duration()-self.fading_duration)
				else:
					self._timestamp.append(self._timestamp[-1] + self.tags[i].duration()-self.fading_duration/2)

	def get_current_position(self):
		""" Get current track number and playing time.

			Returns:
			dict{
				'track': "number of current track on tags list",
				'time': "current position in seconds"
			}
		"""
		if self._my_player is not None:
			player_position = self._my_player.getCurrentPosition()
			i = 0
			try:
				while player_position > self._timestamp[i]:
					i += 1
			except IndexError:
				print('index error')
				raise EndOfPlaylistException()
			if i > 0:
				current_position = player_position - self._timestamp[i - 1]
			else:
				current_position = player_position + self._start_offset
			return {'track': self._track_number + i, 'time': current_position}
		else:
			return {'track': 0, 'time': 0}

	def seek(self, time):
		player_position = self._my_player.getCurrentPosition()
		i = 0
		while player_position > self._timestamp[i]:
			i += 1
		self._track_number += i
		self._start_offset = time
		self._count_timestamps()
		self._my_player.clear()
		del self._my_player
		self.__request_optimizer(self._track_number, time)
		self._my_player.play()

	def add_files(self, files, progressbar=None):
		if type(files[0]) is str:
			for file in files:
				if file[-3:] == 'cue':
					self.tags += CUEindexer(file)
				else:
					file_index = MusicFile(file)
					if file_index.getChapter():
						for i in range(file_index.getChapter()):
							self.tags.append(file_index.getChapter(i))
					else:
						self.tags.append(file_index)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tags += files
		self._playlist_len = len(self.tags)
		self._count_timestamps()

	def __request_optimizer(self, item: int, offset: int = 0):
		start_position = 0
		if self.tags[item].start() > 0:
			start_position = self.tags[item].start()
			duration = None
		else:
			duration = self.tags[item].duration()
		start_position += offset
		if self.playback_mode == PlaybackModeEnum.CROSSFADE:
			self._my_player = player.CrossfadePlayer(
				self,
				samplerate=self.tags[item].sample_rate(),
				fading_duration=self.fading_duration
			)
		else:
			self._my_player = player.GaplessPlayer(
				self,
				samplerate=self.tags[item].sample_rate(),
				buf_len=buf_len
			)
		has_offset_and_duration = start_position > 0 & (duration is not None)
		has_offset = start_position > 0 or self.tags[item].isChapter()
		self._my_player.open_wave_stream(
			self.tags[item].filename(),
			self.tags[item].container(),
			self.tags[item].codec(),
			gain_mode=self._gain_mode,
			offset=start_position if has_offset else None,
			duration=duration if has_offset_and_duration or not has_offset else None
		)

	def is_start(self):
		return self.get_current_position()['track'] == 0

	def _change_playback_mode(self, mode):
		self.playback_mode = mode

	def _change_gain_mode(self, mode):
		self._gain_mode = mode

	def _change_mode(self, func, args):
		if self._my_player is not None:
			current_position = self.get_current_position()
			state = self._my_player.is_playing
			self._my_player.clear()
			del self._my_player
			self._track_number = current_position['track']
			self._start_offset = current_position['time']
			func(*args)
			self._count_timestamps()
			self.__request_optimizer(self._track_number, self._start_offset)
			if state:
				self._my_player.play()
		else:
			func(*args)
			self._count_timestamps()

	def change_playback_mode(self, mode):
		self._change_mode(self._change_playback_mode, (mode,))

	def change_gain_mode(self, mode):
		self._change_mode(self._change_gain_mode, (mode,))

	def is_playing(self):
		if self._my_player is not None:
			return self._my_player.is_playing()
		return False

	def is_end(self):
		if self._my_player is not None:
			return self._my_player.is_end()
		return False

	def next_audio_file(self):
		current_track = self.get_current_position()['track'] + 1
		if len(self.tags) <= current_track:
			raise EndOfPlaylistException()
		if self.tags[current_track].start() > 0:
			start_position = self.tags[current_track].start()
		else:
			start_position = 0
		if self.tags[current_track].iTunSMPB():
			duration = self.tags[current_track].duration()
		else:
			duration = None
		self._my_player.open_wave_stream(
			self.tags[current_track].filename(),
			offset=start_position if start_position > 0 else None,
			duration=duration,
			gain_mode=self._gain_mode,
			acodec=self.tags[current_track].codec(),
			format=self.tags[current_track].container()
		)

	def gui_show_wait_banner(self):
		self._gui.display_loading_banner()

	def gui_hide_wait_banner(self):
		self._gui.hide_loading_banner()

	def serialize(self, filename=None, dirname=None):
		if filename is not None:
			dirname=os.path.dirname(filename)
		serialisableData=[i.serialize(dirname) for i in self.tags]
		if filename is not None:
			fp=open(filename, 'w')
			json.dump(serialisableData, fp)
			fp.close()
			del serialisableData
		else:
			return json.dumps(serialisableData)

	def save_m3u8(self, filename):
		dirname=os.path.dirname(filename)
		if filename is not None:
			fp=open(filename, 'w')
			fp.write('#EXTM3U\n')
			for tag in self.tags:
				fp.write("#EXTINF:{},{} - {}\n".format(int(tag.duration()), tag.artist(), tag.title()))
				fp.write(os.path.relpath(tag.filename(), start=dirname))
				fp.write('\n')
			fp.close()

	def getAlbum(self, album_artist, album):
		new_tags=[]
		for tag in self.tags:
			if tag.album_artist() == album_artist and tag.album() == album:
				new_tags.append(tag)
		return new_tags

	def setAlbumArtistTags(self, tracks, new_album_artist, new_album, disc=None):
		start_pos = 0
		for tag in tracks:
			start_pos = self.tags.index(tag, start_pos)
			self.tags[start_pos].setAlbumArtist(new_album_artist)
			self.tags[start_pos].setAlbum(new_album)
			if disc is not None:
				self.tags[start_pos].setDisc(disc)

	def get_playlist_len(self):
		return self._playlist_len

class DeserialisedPlaylist(Playlist):
	def __init__(self, filename=None, data=None, dirname=None):
		serialisableData = None
		if filename is not None:
			dirname=os.path.dirname(filename)
			fp=open(filename, 'r')
			serialisableData=json.load(fp)
			fp.close()
		elif data is not None:
			serialisableData = json.loads(data)
		self.tags=[DeserializeMusicTrack(i, dirname) for i in serialisableData]
		self._myplayer=None
		self._start_offset=0
		self._timestamp=[]
		self._tracknumber = 0
		self.fading_duration = 10
		self.playback_mode = PlaybackModeEnum.GAPLESS
		self._gui=None

def serizlize_playlist_file(filename, playlist:Playlist, gui):
	outfile = playlist_file_format.PlaylistWriter(filename)
	dirname = os.path.dirname(filename)
	json_data = zlib.compress(playlist.serialize(dirname=dirname).encode("utf-8"))
	outfile.write_chunk(json_data)
	del json_data
	cover_thumbnails = gui.playlist_getCoverThumbnails()
	webp_support = True
	for thumbnail in cover_thumbnails:
		img = None
		if type(thumbnail) is bytes:
			buf = io.BytesIO(thumbnail)
			img = Image.open(buf)
			del buf
		elif type(thumbnail) is Image.Image:
			img = thumbnail
		outbuf = io.BytesIO()
		if webp_support:
			try:
				img.save(outbuf, format="WEBP")
			except KeyError:
				webp_support = False
				outbuf = _encode_webp(img)
		else:
			outbuf = _encode_webp(img)
		outfile.write_chunk(outbuf.getvalue())
		del outbuf
	outfile.close()

def _encode_webp(img):
	commandline = [
		os.path.join(os.path.dirname(sys.argv[0]), 'cwebp'),
		'-o', '-', '--', '-', '-quiet'
	]
	if system()=='Windows':
		process = subprocess.Popen(
			commandline, stdin=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=status_info
		)
	else:
		process = subprocess.Popen(commandline, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
	img.save(process.stdin, format='PNG')
	process.stdin.close()
	outbuf = io.BytesIO(process.stdout.read())
	process.terminate()
	return outbuf

def deserizlize_playlist_file(filename, gui):
	file = playlist_file_format.open_playlist(filename)
	raw_json = file.read_chunk()
	if type(raw_json) is bytes:
		json_data = zlib.decompress(raw_json).decode("utf-8")
	elif raw_json is None:
		file.close()
		raise playlist_file_format.IncorrectPlaylistFile(filename)
	thumbnails = []
	while not file.EOF():
		thumbnails.append(file.read_chunk())
	file.close()
	gui.setPlaylist(DeserialisedPlaylist(data=json_data, dirname=os.path.dirname(filename)),
					cover_thumbnails=thumbnails)