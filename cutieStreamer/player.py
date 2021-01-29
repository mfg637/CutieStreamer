#!/usr/bin/python3
# -*- coding: utf-8 -*-
#player.py by mfg637

import logging
from abc import ABCMeta, abstractmethod

import math
import sounddevice
import struct
import threading

from audiolib import timecode
from . import playlist, streamers
from audiolib.enums import GainModeEnum

logger = logging.getLogger(__name__)


class Player():
	__metaclass__ = ABCMeta

	@abstractmethod
	def __init__(self):
		self._samplecount = 0
		self._buffer = []
		self._blocksize = 1136
		self._buffer_size = self._blocksize*8
		self._samplerate = 0

	def play(self):
		if not self._end:
			if self._outputStream is None:
				self.run()
			self._outputStream.start()
			self.playing=True

	def pause(self):
		self._outputStream.stop()
		self.playing = False

	def _callback(self, outdata, frames, time, status):
		self._samplecount += frames
		data = self.extract_from_buffer()
		if len(data) < frames*8:
			self._end = True
			while len(data) < frames*8:
				data += struct.pack('<f', 0)
			outdata[:] = data[:]
			raise sounddevice.CallbackStop
		else:
			outdata[:] = data

	def run(self):
		i = 0
		while i < 3:
			self._buffer.append(self._streamer.read(self._buffer_size))
			i += 1
		if not self._end:
			self._outputStream = sounddevice.RawOutputStream(
				samplerate=self._samplerate,
				channels=2,
				dtype='float32',
				callback=self._callback,
				blocksize=self._blocksize
			)

	def clear(self):
		if self._outputStream is not None:
			self._outputStream.stop()
			self._outputStream.close()
		self._streamer.close()

	def getCurrentPosition(self):
		start_loading = threading.Thread(target=self.load_buff)
		start_loading.run()
		return self._samplecount/self._samplerate

	def is_playing(self):
		if self._end:
			return False
		if self._outputStream is not None:
			return bool(self._outputStream.active)
		return False

	def is_end(self):
		return self._end

	def extract_from_buffer(self):
		if len(self._buffer) == 0:
			self.load_buff()
		try:
			return self._buffer.pop(0)
		except IndexError:
			self.load_buff()
		return self._buffer.pop(0)

	def open_wave_stream(self, file, format, acodec, gain_mode: GainModeEnum, gains, *, offset=None, duration=None):

		logger.info("Gain mode = %s", gain_mode)
		logger.debug("gains = %s", gains)
		if format == 'ogg' and acodec == 'opus':
			if offset is None:
				self._streamer = streamers.OpusDecoder(
					file,
					self._samplerate,
					offset=offset,
					gain=gains[gain_mode]
				)
			else:
				self._streamer = streamers.FFmpeg(
					file,
					self._samplerate,
					offset=offset,
					duration=duration,
					gain=gains[gain_mode]
				)
		else:
			self._streamer = streamers.FFmpeg(
				file,
				self._samplerate,
				offset=offset,
				duration=duration,
				gain=gains[gain_mode]
			)

	@abstractmethod
	def load_buff(self):
		pass


class GaplessPlayer(Player):

	def __init__(self, playlist, samplerate=44100, buf_len=None):
		self._playlist_instance=playlist
		if samplerate>44100:
			self._samplerate=samplerate
		else:
			self._samplerate=44100
		self._buf_len = 0
		if buf_len is None:
			self._buf_len = int(math.ceil(self._samplerate/1136))
		else:
			if ':' in buf_len:
				self._buf_len = int(math.ceil(timecode.parse(buf_len)*self._samplerate/1136))
			elif buf_len[-1] == 's':
				self._buf_len = int(math.ceil(int(buf_len[:-1])*self._samplerate/1136))
			else:
				self._buf_len = int(math.ceil(float(buf_len)))
		self._blocksize = 1136
		self._buffer_size=self._blocksize*8
		self._ffmpeg=None
		self._streamer = None
		self.playing=False
		self._closing=False
		self._first_frame=True
		self._outputStream=None
		self._samplecount=0
		self._end=False
		self._buffer=[]
		self._fill_buffer=True

	def load_buff(self):
		if self._fill_buffer:
			while len(self._buffer) < self._buf_len:
				data = self._streamer.read(self._buffer_size)
				if (len(data)<self._buffer_size):
					self._fill_buffer=False
					thread=threading.Thread(target=self.open_next_file, args=(data,))
					thread.run()
				else:
					self._buffer.append(data)

	def open_next_file(self, data):
		try:
			self._playlist_instance.next_audio_file()
		except playlist.EndOfPlaylistException:
			pass
		else:
			data += self._streamer.read(self._buffer_size-len(data))
		finally:
			self._buffer.append(data)
			self._fill_buffer=True

	def streamActive(self):
		return self._outputStream.active()


class CrossfadePlayer(Player):
	def __init__(self, playlist, samplerate=44100, buf_len=None, *, fading_duration=10):
		self._playlist_instance=playlist
		if samplerate>44100:
			self._samplerate=samplerate
		else:
			self._samplerate=44100
		self._blocksize = 1136
		self._buffer_size=self._blocksize*8
		self._ffmpeg=None
		self._streamer = None
		self.playing=False
		self._closing=False
		self._first_frame=True
		self._outputStream=None
		self._samplecount=0
		self._end=False
		self._buffer=[]
		self._fill_buffer=True

	def load_buff(self):
		if self._fill_buffer:
			i=0
			while (len(self._buffer)<math.ceil(self._samplerate/1136*30)) \
				and (i<=math.ceil(self._samplerate/1136)):
				data = self._streamer.read(self._buffer_size)
				if (len(data)<self._buffer_size):
					self._fill_buffer = False
					try:
						self._playlist_instance.next_audio_file()
						self._buffer.append(data)
						thread=threading.Thread(target=self.__crossfadeAudio)
						thread.start()
					except playlist.EndOfPlaylistException:
						self._fill_buffer = True
						self._buffer.append(data)
						return None
				else:
					# sometimes crossfading process start working
					# before buffer loader is done.
					# in that case wave data has been droped
					if self._fill_buffer:
						self._buffer.append(data)
				i += 1

	def __crossfadeAudio(self, fading_duration=10):
		if len(self._buffer)>math.ceil(self._samplerate/1136*fading_duration):
			step=1/(self._samplerate*fading_duration)
		else:
			step=1/(1136*len(self._buffer))
			self.pause()
		fadein=0
		fadeout=1
		for i in range(math.ceil(self._samplerate/1136*fading_duration), 0, -1):
			subbuf=[]
			for j in range(1136):
				for channel in range(2):
					data = struct.unpack('<f', self._streamer.read(4))[0]
					# select 4 bytes (sample size)
					# 8 - frame size
					source=self._buffer[-i][j*8+channel*4:j*8+channel*4+4]
					if len(source)<4:
						sourceval=0
					else:
						sourceval=(struct.unpack('<f', source)[0])
						sourceval*=fadeout
					data*=fadein
					subbuf.append(sourceval+data)
				fadein+=step
				fadeout-=step
			self._buffer[-i]=b''
			for value in subbuf:
				self._buffer[-i]+=struct.pack('<f', value)
		self._fill_buffer=True
		if not self.is_playing:
			self.play()

	def streamActive(self):
		return self._outputStream.active()