#!/usr/bin/python3
# -*- coding: utf-8 -*-
#cutieStreamer.py by mfg637

import sys, time, os
from audiolib import tagIndexer
from cutieStreamer import playlist, gui
import logging

if len(sys.argv)>1:
	_playlist=[]
	pointer = 1
	#for item in sys.argv[1:]:
	while pointer < len(sys.argv):
		if sys.argv[pointer][:2] == '--':
			if sys.argv[pointer][2:] == 'buf_len':
				pointer += 1
				playlist.buf_len = sys.argv[pointer]
			elif sys.argv[pointer][2:] == 'log':
				pointer += 1
				logging.basicConfig(level=sys.argv[pointer])
		elif os.path.isdir(sys.argv[pointer]):
			_playlist += tagIndexer.indexer(sys.argv[pointer])
		elif os.path.isfile(sys.argv[pointer]):
			if sys.argv[pointer][-5:]=='.cspl':
				_playlist = sys.argv[pointer]
			elif sys.argv[pointer][-19:]=='.cutieStreamer.json':
				_playlist = playlist.DeserialisedPlaylist(sys.argv[pointer])
			elif os.path.splitext(sys.argv[pointer])[1]==".cue":
				_playlist += tagIndexer.CUEindexer(sys.argv[pointer])
			elif os.path.splitext(sys.argv[pointer])[1]=='.m3u':
				_playlist += tagIndexer.m3u_indexer(sys.argv[pointer])
			elif os.path.splitext(sys.argv[pointer])[1]=='.m3u8':
				_playlist += tagIndexer.m3u_indexer(sys.argv[pointer], unicode=True)
			else:
				FileIndex=tagIndexer.MusicFile(sys.argv[pointer])
				if FileIndex.getChapter():
					for i in range(FileIndex.getChapter()):
						_playlist.append(FileIndex.getChapter(i))
				else:
					_playlist.append(FileIndex)
		pointer += 1
	if type(_playlist) is playlist.DeserialisedPlaylist:
		print(type(_playlist))
		myPlaylist = _playlist
		GUI=gui.GUI(myPlaylist, async_playlist_load=False)
	elif type(_playlist) is str and _playlist[-5:]=='.cspl':
		GUI = gui.GUI(_playlist)
	else:
		myPlaylist = playlist.Playlist(_playlist)
		GUI=gui.GUI(myPlaylist)
else:
	GUI=gui.GUI(None)