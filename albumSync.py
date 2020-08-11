#!/usr/bin/python3
# -*- coding: utf-8 -*-
#exebutable script file writed by mfg637

import sys, subprocess, os, shutil, platform, re, time, ffmpeg
#from audiolib import tagIndexer, formatNum
from audiolib.tagIndexer import MusicFile, indexer
import converter
from imglib import resample
from pathlib import Path
if platform.system()=='Windows':
	from multiprocessing.dummy import Pool
else:
	from multiprocessing import Pool


wdir=os.getcwd()


srcindex=[]
dirlist=[]
ignoreCUE=False
n=len(sys.argv)
i=1

disc=None
album=None
album_artist=None
custom_tags=[]

while i<n:
	if sys.argv[i][:2]=="--":
		if sys.argv[i][2:]=="outdir":
			i+=1
			converter.outdir=sys.argv[i]
		elif sys.argv[i][2:]=="ignoreCUE":
			ignoreCUE=True
		elif sys.argv[i][2:]=="quality":
			i+=1
			converter.aacenc.qscale=int(sys.argv[i])
		elif sys.argv[i][2:]=="disc":
			i+=1
			disc=sys.argv[i]
		elif sys.argv[i][2:]=="album":
			i+=1
			album=sys.argv[i]
		elif sys.argv[i][2:]=="album_artist":
			i+=1
			album_artist=sys.argv[i]
	else:
		dirlist.append(sys.argv[i])
		custom_tag={}
		if disc is not None:
			custom_tag['disc']=disc
			disc=None
		if album is not None:
			custom_tag['album']=album
			album=None
		if album_artist is not None:
			custom_tag['album artist']=album_artist
			album_artist=None
		custom_tags.append(custom_tag)
	i+=1
if not os.path.exists(converter.outdir):
	print('[albumSync.py] directory '+converter.outdir+' is not exist! May be you need mount your device?')
	exit()

def indexSongs(i):
	dt=indexer(dirlist[i])
	songs=[]
	for elem in dt:
		if elem.getChapter():
			x=0
			while x<elem.getChapter():
				songs.append(disc.getChapter(i))
				x+=1
		else:
			songs.append(elem)
	for song in songs:
		if 'album' in custom_tags[i]:
			song.setAlbum(custom_tags[i]['album'])
		if 'album artist' in custom_tags[i]:
			song.setAlbumArtist(custom_tags[i]['album artist'])
		if 'disc' in custom_tags[i]:
			song.setDisc(custom_tags[i]['disc'])
	return songs

scanpool = Pool()
scanresults=scanpool.map(indexSongs, range(len(dirlist)))
scanpool.close()
scanpool.join()
for result in scanresults:
	srcindex+=result
del scanresults

albums=set()

for song in srcindex:
	if song.album() not in albums:
		albums.add(song.album())
		aldir=converter.strtofile(song.album_artist())+' - '+converter.strtofile(song.album())
		if not os.path.exists(os.path.join(converter.outdir, aldir)):
			os.mkdir(os.path.join(converter.outdir, aldir))
		if song.hasEmbededCover():
			streamer=ffmpeg.getPPM_Stream(song.filename())
			resample(streamer.stdout, os.path.join(converter.outdir, aldir, 'folder.jpg'), max=200)
		elif len(song.cover()):
			resample(song.cover(),
				os.path.join(converter.outdir, aldir, 'folder.jpg'),
				max=200)

os.chdir(wdir)



audioConverterPool = Pool()
audioConverterPool.map(converter.convertAudio, srcindex)
audioConverterPool.close()
audioConverterPool.join()