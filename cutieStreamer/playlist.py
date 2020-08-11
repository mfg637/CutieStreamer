#!/usr/bin/python3
# -*- coding: utf-8 -*-
#playlist by mfg637

import json, os, zlib, struct, io, sys
from . import player, playlist_file_format
from PIL import Image
from audiolib.tagIndexer import MusicFile, CUEindexer, DeserializeMusicTrack, m3u_indexer
import subprocess
from platform import system

if system()=='Windows':
	si = subprocess.STARTUPINFO()
	si.dwFlags |= subprocess.STARTF_USESHOWWINDOW


class EndOfPlaylistException(Exception):
	def __init__(self):
		pass


buf_len = None


class Playlist():
	"""Class describes playlist and is a wrapper for player.
		Only one instance can be displayed in gui."""
	def __init__(self, files, progressbar=None):
		self.tags=[]
		if type(files[0]) is str:
			for file in files:
				if os.path.splitext(file)[1]=='.cue':
					self.tags += CUEindexer(file)
				elif os.path.splitext(file)[1]=='.m3u':
					self.tags += m3u_indexer(file)
				elif os.path.splitext(file)[1]=='.m3u8':
					self.tags += m3u_indexer(file, unicode=True)
				else:
					FileIndex=MusicFile(file)
					if FileIndex.getChapter():
						for i in range(FileIndex.getChapter()):
							self.tags.append(FileIndex.getChapter(i))
					else:
						self.tags.append(FileIndex)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tags=files
		self._myplayer=None
		self._start_offset=0
		self._timestamp=[]
		self._tracknumber = 0
		self.fading_duration = 10
		self.playback_mode = 'gapless'
		self._gui=None
		self._playlist_len = len(self.tags)

	def setGui(self, link):
		"Bind GUI class for this playlist"
		self._gui=link

	def PlayFromItem(self, item: int):
		if self._myplayer is not None:
			self._myplayer.clear()
			del self._myplayer
		self._tracknumber = item
		self._start_offset = 0
		self._count_timestamps()
		self.__request_optimizer(item)
		self._myplayer.play()

	def play(self):
		if (self._myplayer is None) or (self._myplayer.isEnd()):
			self.__request_optimizer(0)
			self._start_offset=0
			self._tracknumber = 0
			self._count_timestamps()
		self._myplayer.play()

	def pause(self):
		self._myplayer.pause()

	def state(self):
		if self._myplayer is None:
			return False
		else:
			return self._myplayer.playing

	def stop(self):
		self._myplayer.clear()
		del self._myplayer
		self._myplayer=None

	def clear(self):
		if self._myplayer is not None:
			self._myplayer.clear()
			del self._myplayer
			self._myplayer=None

	def _count_timestamps(self):
		self._timestamp=[self.tags[self._tracknumber].duration()-self._start_offset]
		if self.playback_mode=='gapless':
			for i in range(self._tracknumber+1, len(self.tags)):
				self._timestamp.append(self._timestamp[-1]+
					self.tags[i].duration())
		elif self.playback_mode=='crossfade':
			self._timestamp[0]-=self.fading_duration/2
			for i in range(self._tracknumber+1, len(self.tags)):
				if i<(len(self.tags)-1):
					self._timestamp.append(self._timestamp[-1]+
						self.tags[i].duration()-self.fading_duration)
				else:
					self._timestamp.append(self._timestamp[-1]+
						self.tags[i].duration()-self.fading_duration/2)

	def currentPosition(self):
		""" Get current track number and playing time.

			Returns:
			dict{
				'track': "number of current track on tags list",
				'time': "curent position in seconds"
			}
		"""
		if self._myplayer is not None:
			player_position=self._myplayer.getCurrentPosition()
			i=0
			try:
				while (player_position>self._timestamp[i]):
					i+=1
			except IndexError:
				print('index error')
				raise EndOfPlaylistException()
			if i>0:
				currentPosition=player_position-self._timestamp[i-1]
			else:
				currentPosition=player_position+self._start_offset
			return {'track': self._tracknumber+i, 'time': currentPosition}
		else:
			return {'track': 0, 'time': 0}

	def seek(self, time):
		player_position=self._myplayer.getCurrentPosition()
		i=0
		while (player_position>self._timestamp[i]):
			i+=1
		self._tracknumber+=i
		self._start_offset=time
		self._count_timestamps()
		self._myplayer.clear()
		del self._myplayer
		self.__request_optimizer(self._tracknumber, time)
		self._myplayer.play()

	def addFiles(self, files, progressbar = None):
		if type(files[0]) is str:
			for file in files:
				if file[-3:]=='cue':
					self.tags += CUEindexer(file)
				else:
					FileIndex=MusicFile(file)
					if FileIndex.getChapter():
						for i in range(FileIndex.getChapter()):
							self.tags.append(FileIndex.getChapter(i))
					else:
						self.tags.append(FileIndex)
				if progressbar is not None:
					progressbar.step()
					progressbar.update_idletasks()
		else:
			self.tags+=files
		self._playlist_len = len(self.tags)
		self._count_timestamps()

	def __request_optimizer(self, item: int, offset: int=0):
		start_position = 0
		if self.tags[item].start()>0:
			start_position = self.tags[item].start()
			duration = None
		else:
			duration = self.tags[item].duration()
		start_position += offset
		if self.playback_mode == 'crossfade':
			self._myplayer = player.CrossfadePlayer(self,
				samplerate = self.tags[item].sample_rate(),
				fading_duration=self.fading_duration)
		else:
			self._myplayer=player.GaplessPlayer(self, samplerate=self.tags[item].sample_rate(), buf_len=buf_len)
		if start_position>0 & (duration is not None):
			self._myplayer.openWaveStream(self.tags[item].filename(), self.tags[item].container(),
				self.tags[item].codec(), offset=start_position, duration=duration)
		elif start_position>0 or self.tags[item].isChapter():
			self._myplayer.openWaveStream(self.tags[item].filename(), self.tags[item].container(),
				self.tags[item].codec(), offset=start_position)
		else:
			self._myplayer.openWaveStream(self.tags[item].filename(), self.tags[item].container(),
				self.tags[item].codec(), duration=duration)

	def isStart(self):
		return self.currentPosition()['track']==0

	def change_playback_mode(self, mode):
		if self._myplayer is not None:
			currentPosition=self.currentPosition()
			state=self._myplayer.isPlaying
			self._myplayer.clear()
			del self._myplayer
			self._tracknumber=currentPosition['track']
			self._start_offset=currentPosition['time']
			self.playback_mode=mode
			self._count_timestamps()
			self.__request_optimizer(self._tracknumber, self._start_offset)
			if state:
				self._myplayer.play()
		else:
			self.playback_mode=mode
			self._count_timestamps()

	def isPlaying(self):
		if self._myplayer is not None:
			return self._myplayer.isPlaying()
		return False

	def isEnd(self):
		if self._myplayer is not None:
			return self._myplayer.isEnd()
		return False
	def nextAudioFile(self):
		currentTrack = self.currentPosition()['track']+1
		if len(self.tags)<=currentTrack:
			raise EndOfPlaylistException()
		if self.tags[currentTrack].start()>0:
			start_position=self.tags[currentTrack].start()
		else:
			start_position=0
		if self.tags[currentTrack].iTunSMPB():
			duration = self.tags[currentTrack].duration()
		else:
			duration = None
		if start_position>0:
			self._myplayer.openWaveStream(
				self.tags[currentTrack].filename(),
				offset=start_position, duration=duration,
				acodec=self.tags[currentTrack].codec(),
				format=self.tags[currentTrack].container())
		else:
			self._myplayer.openWaveStream(self.tags[currentTrack].filename(),
				self.tags[currentTrack].container(),
				self.tags[currentTrack].codec(), duration=duration)

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
		self.playback_mode = 'gapless'
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
			commandline, stdin=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=si
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