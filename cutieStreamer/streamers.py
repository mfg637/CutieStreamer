#!/usr/bin/python3
# -*- coding: utf-8 -*-
# streamers.py by mfg637

import logging
import subprocess
from platform import system
from abc import ABCMeta, abstractmethod
from .playlist import GainModeEnum

logger = logging.getLogger(__name__)

if system() == 'Windows':
	status_info = subprocess.STARTUPINFO()
	status_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW


class Streamer:
	__metaclass__ = ABCMeta

	@abstractmethod
	def __init__(self):
		self._open = True
		self._streamer = subprocess.Popen([], stdout=subprocess.PIPE)

	def read(self, size: int):
		return self._streamer.stdout.read(size)

	def close(self):
		self._streamer.stdout.close()
		self._streamer.terminate()
		self._open = False

	def __del__(self):
		if self._open:
			self.close()


class FFmpeg(Streamer):
	def __init__(self, file, samplerate, gain, *, offset=None, duration=None):
		global status_info
		self._open = True
		commandline = ['ffmpeg']
		if offset is None:
			if duration is not None:
				commandline += ['-t', str(duration)]
		else:
			commandline += ['-ss', str(offset)]
			if duration is not None:
				commandline += ['-t', str(duration-offset)]
		commandline += [
			'-i', file,
			'-vn']
		if gain != GainModeEnum.NONE:
			commandline += ["-af"]
			if gain == GainModeEnum.REPLAY_GAIN:
				commandline += ["volume=replaygain=album"]
			else:
				commandline += ["volume={}".format(gain)]
		commandline += [
			'-acodec', 'pcm_f32le',
			'-ac', '2',
			'-ar', str(samplerate),
			'-f', 'f32le',
			'-',
			'-loglevel', 'quiet',
			'-hide_banner']
		logger.debug("ffmpeg commandline: %s", commandline)
		if system() == 'Windows':
			try:
				self._streamer = subprocess.Popen(commandline, stdout=subprocess.PIPE, startupinfo=status_info)
			except OSError:
				status_info = None
				self._streamer = subprocess.Popen(commandline, stdout=subprocess.PIPE)
		else:
			self._streamer = subprocess.Popen(commandline, stdout=subprocess.PIPE)


class OpusDecoder(Streamer):
	def __init__(self, file, samplerate, gain, *, offset=None):
		global status_info
		self._open = True
		commandline = ['opusdec', '--float', '--rate', str(samplerate)]
		if gain == GainModeEnum.REPLAY_GAIN:
			commandline += ["--gain", "5 dB"]
		commandline += [file, '-']
		logger.debug("opusdec commandline: %s", commandline)
		if system() == 'Windows':
			try:
				self._streamer = subprocess.Popen(
					commandline,
					stdout=subprocess.PIPE,
					stderr=subprocess.DEVNULL,
					startupinfo=status_info
				)
			except OSError:
				status_info = None
				self._streamer = subprocess.Popen(
					commandline,
					stdout=subprocess.PIPE,
					stderr=subprocess.DEVNULL
				)
		else:
			self._streamer = subprocess.Popen(
				commandline,
				stdout=subprocess.PIPE,
				stderr=subprocess.DEVNULL
			)
		if offset is not None:
			self._streamer.stdout.read(int(round(offset*samplerate))*8)
