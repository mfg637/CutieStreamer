#!/usr/bin/python3
# -*- coding: utf-8 -*-

import subprocess, os, json, platform, exceptions
from platform import system

if system()=="Windows":
	si = subprocess.STARTUPINFO()
	si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

def getOutput(commandline):
	global si
	if system()=="Windows":
		try:
			return subprocess.check_output(commandline, startupinfo=si)
		except OSError:
			si=None
			return subprocess.check_output(commandline)
	else:
		return subprocess.check_output(commandline)

def probe(source):
	try:
		commandline = ['ffprobe', '-loglevel', '24', '-hide_banner', '-print_format', 'json',
			'-show_format', '-show_streams', '-show_chapters', os.path.realpath(source)]
		return json.loads(str(getOutput(commandline),'utf-8'))
	except UnicodeEncodeError:
		raise exceptions.invalidFilename(source)

def getPPM_commandline(source:str, size, force, index):
	commandline = ['ffmpeg', '-loglevel', '24', '-i', os.path.realpath(source)]
	if index is not None:
		commandline += ['-map', '0:{}'.format(index)]
	commandline += ['-vframes', '1']
	if size is not None:
		commandline+=['-vf']
		if force:
			commandline += ['scale=size='+size]
		else:
			size=size.split('x')
			commandline += [('scale=w=\'min('+size[0]+', iw)\':h=\'min('+size[1]+', ih)\''+
				':force_original_aspect_ratio=decrease')]
	commandline+=['-vcodec', 'ppm', '-f', 'image2pipe', '-']
	return commandline

def getPPM_Image(source:str, size=None, force=False, index=None):
	commandline = getPPM_commandline(source, size, force, index)
	return getOutput(commandline)

def getPPM_Stream(source:str, size=None, force=False, index=None):
	commandline = getPPM_commandline(source, size, force, index)
	return subprocess.Popen(commandline, stdout=subprocess.PIPE)

def getJPEG_Image(source:str, size=None, quantizer=3, force=False):
	commandline = ['ffmpeg', '-loglevel', '24', '-i', os.path.realpath(source),
		'-vframes', '1']
	if size is not None:
		commandline+=['-vf']
		if force:
			commandline += ['scale=size='+size]
		else:
			size=size.split('x')
			commandline += [('scale=w=\'min('+size[0]+', iw)\':h=\'min('+size[1]+', ih)\''+
				':force_original_aspect_ratio=decrease')]
	commandline+=['-q:v', str(quantizer), '-f', 'image2pipe', '-']
	return getOutput(commandline)

def probeCDDA(source):
	commandline = ['ffprobe', '-loglevel', '24', '-hide_banner', '-print_format', 'json',
		'-show_format', '-show_streams', '-show_chapters', '-f', 'libcdio', '-i',
			os.path.realpath(source)]
	return json.loads(str(getOutput(commandline),'utf-8'))