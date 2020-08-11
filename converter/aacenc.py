#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os, subprocess
from platform import system
from .exceptions import NotFountAvaibleEncoders

if system()=='Windows':
	si = subprocess.STARTUPINFO()
	si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

class AACencException(Exception):
	pass



qaac=0
try:
	if system()=='Windows':
		qaac=subprocess.call(['qaac', '--check'], startupinfo=si)
	else:
		qaac=subprocess.call(['qaac', '--check'])
except FileNotFoundError:
	qaac=1
try:
	if system()=='Windows':
		subprocess.call(['fdkaac', '--help'], startupinfo=si)
	else:
		subprocess.call(['fdkaac', '--help'])
except FileNotFoundError:
	fdkaac=1
else:
	fdkaac=0
if qaac & fdkaac:
	raise NotFountAvaibleEncoders()
qscale=4

class AACenc:
	def __init__(self, input, outfile, *, title=None, artist=None, albumArtist=None,
		album=None, genre=None, date=None, track=None, disk=None):
		if qaac==0:
			self.__qaac(input, outfile, title=title, artist=artist, albumArtist=albumArtist,
				album=album, genre=genre, date=date, track=track, disk=disk)
		elif fdkaac==0:
			self.__fdkaac(input, outfile, title=title, artist=artist,
				albumArtist=albumArtist, album=album, genre=genre, date=date, track=track, disk=disk)
	def __qaac(self, input, outfile, *, title=None, artist=None, albumArtist=None,
		album=None, genre=None, date=None, track=None, disk=None):
		qvalue=[0, 27, 36, 45, 64, 100, 109]
		VBR=qvalue[qscale]
		commandline=['qaac', '-o', outfile, '-V', str(VBR)]
		if title:
			commandline+=['--title', title]
		if artist:
			commandline+=['--artist', artist]
		if albumArtist:
			commandline+=['--band', albumArtist]
		if album:
			commandline+=['--album', album]
		if genre:
			commandline+=['--genre', genre]
		if date:
			commandline+=['--date', date]
		if track:
			commandline+=['--track', track]
		if disk:
			commandline+=['--disk', disk]
		if type(input) is bytes:
			commandline+=['-']
			self._encoder=subprocess.Popen(commandline, stdin=subprocess.PIPE)
			self.write(input)
		else:
			commandline+=[input]
	def __fdkaac(self, input, outfile, *, title=None, artist=None, albumArtist=None,
		album=None, genre=None, date=None, track=None, disk=None):
		qrange=[2,3,3,4,4,5,5]
		bandwidth_range=[None, None, 16000, 16000, 18000, 20000, None]
		VBR=qscale
		commandline=['fdkaac', '-o', outfile, '-m', str(qrange[VBR])]
		if bandwidth_range[VBR] is not None:
			commandline+=['-w', str(bandwidth_range[VBR])]
		if title:
			commandline+=['--title', title]
		if artist:
			commandline+=['--artist', artist]
		if albumArtist:
			commandline+=['--album-artist', albumArtist]
		if album:
			commandline+=['--album', album]
		if genre:
			commandline+=['--genre', genre]
		if date:
			commandline+=['--date', date]
		if track:
			commandline+=['--track', track]
		if disk:
			commandline+=['--disk', disk]
		if type(input) is bytes:
			commandline+=['-']
			self._encoder=subprocess.Popen(commandline, stdin=subprocess.PIPE)
			self.write(input)
		else:
			commandline+=[input]
	def write(self, data:bytes):
		self._encoder.stdin.write(data)
	def closePIPE(self):
		self._encoder.stdin.close()