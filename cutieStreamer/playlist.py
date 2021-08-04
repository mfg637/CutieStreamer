#!/usr/bin/python3
# -*- coding: utf-8 -*-
# playlist by mfg637

import io
import json
import logging
import os
import subprocess
import sys
import zlib
from platform import system
import enum
import gui
import pathlib

import r128gain
from PIL import Image

from audiolib.enums import GainModeEnum
from audiolib.tagIndexer import builders, DeserializeMusicTrack, m3u_indexer, MusicTrack
from . import player, playlist_file_format

logger = logging.getLogger(__name__)

if system() == 'Windows':
	status_info = subprocess.STARTUPINFO()
	status_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW


class EndOfPlaylistException(Exception):
	def __init__(self):
		pass


class PlaybackModeEnum(enum.Enum):
	GAPLESS = enum.auto()
	CROSSFADE = enum.auto()


buf_len = None


class Playlist:
	"""Class describes playlist and is a wrapper for player.
		Only one instance can be displayed in gui."""
	def __init__(self, files, progressbar=None):
		self.tracks = []
		if type(files[0]) is str:
			for file in files:
				if os.path.splitext(file)[1] == '.cue':
					self.tracks += builders.MusicTrackBuilder.cue_sheet_indexer(file)
				elif os.path.splitext(file)[1] == '.m3u':
					self.tracks += m3u_indexer(file)
				elif os.path.splitext(file)[1] == '.m3u8':
					self.tracks += m3u_indexer(file, unicode=True)
				else:
					file_index = builders.MusicTrackBuilder.track_file_builder(pathlib.Path(file))
					if type(file_index) == list:
						self.tracks.extend(file_index)
					else:
						self.tracks.append(file_index)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tracks = files
		self._my_player = None
		self._start_offset = 0
		self._timestamp = []
		self._track_number = 0
		self.fading_duration = 10
		self.playback_mode = PlaybackModeEnum.GAPLESS
		self._gain_mode = GainModeEnum.NONE
		self._gui = None
		self._playlist_len = len(self.tracks)

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
		self._timestamp = [self.tracks[self._track_number].duration() - self._start_offset]
		if self.playback_mode == PlaybackModeEnum.GAPLESS:
			for i in range(self._track_number + 1, len(self.tracks)):
				self._timestamp.append(self._timestamp[-1] + self.tracks[i].duration())
		elif self.playback_mode == PlaybackModeEnum.CROSSFADE:
			self._timestamp[0] -= self.fading_duration/2
			for i in range(self._track_number + 1, len(self.tracks)):
				if i < (len(self.tracks) - 1):
					self._timestamp.append(self._timestamp[-1] + self.tracks[i].duration() - self.fading_duration)
				else:
					self._timestamp.append(self._timestamp[-1] + self.tracks[i].duration() - self.fading_duration / 2)

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
					self.tracks += builders.MusicTrackBuilder.cue_sheet_indexer(file)
				else:
					file_index = builders.MusicTrackBuilder.track_file_builder(pathlib.Path(file))
					if type(file_index) == list:
						self.tracks.extend(file_index)
					else:
						self.tracks.append(file_index)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tracks += files
		self._playlist_len = len(self.tracks)
		self._count_timestamps()

	def __request_optimizer(self, item: int, offset: int = 0):
		start_position = 0
		if self.tracks[item].start() > 0:
			start_position = self.tracks[item].start()
			duration = None
		else:
			duration = self.tracks[item].duration()
		start_position += offset
		if self.playback_mode == PlaybackModeEnum.CROSSFADE:
			self._my_player = player.CrossfadePlayer(
				self,
				samplerate=self.tracks[item].sample_rate(),
				fading_duration=self.fading_duration
			)
		else:
			self._my_player = player.GaplessPlayer(
				self,
				samplerate=self.tracks[item].sample_rate(),
				buf_len=buf_len
			)
		has_offset_and_duration = start_position > 0 & (duration is not None)
		has_offset = start_position > 0
		self._my_player.open_wave_stream(
			self.tracks[item].filename(),
			self.tracks[item].container(),
			self.tracks[item].codec(),
			gain_mode=self._gain_mode,
			gains=self.tracks[item].get_gain_levels(),
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
		if len(self.tracks) <= current_track:
			raise EndOfPlaylistException()
		if self.tracks[current_track].start() > 0:
			start_position = self.tracks[current_track].start()
		else:
			start_position = 0
		if self.tracks[current_track].iTunSMPB():
			duration = self.tracks[current_track].duration()
		else:
			duration = None
		self._my_player.open_wave_stream(
			self.tracks[current_track].filename(),
			offset=start_position if start_position > 0 else None,
			duration=duration,
			gain_mode=self._gain_mode,
			gains=self.tracks[current_track].get_gain_levels(),
			acodec=self.tracks[current_track].codec(),
			format=self.tracks[current_track].container()
		)

	def gui_show_wait_banner(self):
		self._gui.display_loading_banner()

	def gui_hide_wait_banner(self):
		self._gui.hide_loading_banner()

	def serialize(self, filename=None, dirname=None):
		if filename is not None:
			dirname=os.path.dirname(filename)
		serialisableData=[i.serialize(dirname) for i in self.tracks]
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
			for track in self.tracks:
				tags = track.get_tags_list()
				fp.write("#EXTINF:{},{} - {}\n".format(int(track.duration()), tags.artist(), tags.title()))
				fp.write(os.path.relpath(track.filename(), start=dirname))
				fp.write('\n')
			fp.close()

	def getAlbum(self, album_artist, album):
		new_tracks = []
		for track in self.tracks:
			tags = track.get_tags_list()
			if tags.album_artist() == album_artist and tags.album() == album:
				new_tracks.append(track)
		return new_tracks

	def setAlbumArtistTags(self, tracks, new_album_artist, new_album, disc=None):
		start_pos = 0
		for tag in tracks:
			start_pos = self.tracks.index(tag, start_pos)
			self.tracks[start_pos].setAlbumArtist(new_album_artist)
			self.tracks[start_pos].setAlbum(new_album)
			if disc is not None:
				self.tracks[start_pos].set_disc(disc)

	def get_playlist_len(self):
		return self._playlist_len

	def r128_playlist_scan(self, callback:gui.dialogues.LoadingBanner):
		if callback is not None:
			callback.set_window_title("R128 GAIN SCAN")
			callback.set_length(self._playlist_len)
			logger.debug("playlist lenght %s", self._playlist_len)
		albums = dict()
		ungrouped_tracks = list()
		for track in self.tracks:
			tags = track.get_tags_list()
			if tags.album() is not None:
				album_key = (tags.album(), tags.album_artist())
				if album_key not in albums:
					albums[album_key] = list()
				albums[album_key].append(track)
			else:
				ungrouped_tracks.append(track.filename())
		logger.debug("albums: %s", albums)
		logger.debug("tracks: %s", ungrouped_tracks)
		for album in albums:
			file_list = list()
			for track in albums[album]:
				fname = str(pathlib.Path(track.filename()).absolute())
				if fname not in file_list:
					file_list.append(fname)
			logger.debug("input_files: %s", file_list)
			scan_results = r128gain.scan(file_list, album_gain=True)
			logger.debug("scan results: %s", scan_results)
			for track in albums[album]:
				fname = str(pathlib.Path(track.filename()).absolute())
				track.set_r128_track_gain(scan_results[fname][0])
				track.set_r128_album_gain(scan_results[0][0])
			if callback is not None:
				value = len(albums[album]) + callback.get_value()
				logger.debug("callback value set = %s", value)
				callback.set_value(value)
		logger.debug("input_files: %s", ungrouped_tracks)
		scan_results = r128gain.scan(ungrouped_tracks, album_gain=False)
		logger.debug("scan results: %s", scan_results)
		for track in ungrouped_tracks:
			track.set_r128_track_gain(scan_results[track.filename()][0])
		value = len(ungrouped_tracks) + callback.get_value()
		logger.debug("callback increment: %s", value)
		callback.set_value(value)
		logger.info("Gain scan done")


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
		self.tracks=[DeserializeMusicTrack(i, dirname) for i in serialisableData]
		self._my_player = None
		self._start_offset = 0
		self._timestamp = []
		self._track_number = 0
		self.fading_duration = 10
		self.playback_mode = PlaybackModeEnum.GAPLESS
		self._gui = None
		self._gain_mode = GainModeEnum.NONE
		self._playlist_len = len(self.tracks)

def serizlize_playlist_file(filename, playlist:Playlist, gui):
	outfile = playlist_file_format.PlaylistWriter(filename)
	dirname = os.path.dirname(filename)
	json_data = zlib.compress(playlist.serialize(dirname=dirname).encode("utf-8"))
	outfile.write_chunk(json_data)
	del json_data
	cover_thumbnails = gui.playlist__get_cover_thumbnails()
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
	gui.set_playlist(DeserialisedPlaylist(data=json_data, dirname=os.path.dirname(filename)),
					 cover_thumbnails=thumbnails)