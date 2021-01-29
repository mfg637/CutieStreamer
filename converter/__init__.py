#!/usr/bin/python3
# -*- coding: utf-8 -*-

from pathlib import Path
import subprocess, os, re
from imglib import resample
import ffmpeg_prober
import converter.exceptions

try:
	from . import aacenc
except converter.exceptions.NotFountAvaibleEncoders:
	aacenc = None
else:
	outdir = ''

	def strtofile(somestr):
		output=re.sub(r'[^a-zA-Z0-9_ а-яА-Я\-]', '', somestr)
		output=' '.join(output.split())
		return output

	def convertAudio(song):
		if song.disc():
			name=os.path.join(outdir,
							  "{} - {}".format(strtofile(song.album_artist()), strtofile(song.album())),
							  "{}{} {}".format(song.disc(), song.track(), strtofile(song.title())[:42])
							  )
		else:
			name=os.path.join(outdir,
							  "{} - {}".format(strtofile(song.album_artist()), strtofile(song.album())),
							  "{} {}".format(song.track(), strtofile(song.title())[:43])
							  )
		ffmetadata=song.ffmetamarkup()
		commandline=['ffmpeg']
		if Path(song.filename()).is_block_device():
			commandline+=['-f', 'libcdio']
		commandline += ['-ss', str(song.start()), '-t', str(song.duration()),
						'-i', song.filename()]
		if song.codec() in set(["mp3", "aac"]) and (aacenc.qscale>=5 or song.bitrate()<310):
			commandline+=['-i', '-', '-map_metadata', '1', '-map_chapters', '-1', '-vn', '-acodec', 'copy']
			if song.codec()=="mp3":
				commandline+=[name+'.mp3']
			else:
				commandline+=[name+'.m4a']
		else:
			commandline+=[	'-map_metadata', '-1', '-map_chapters', '-1', '-vn',
							  '-ac', '2', '-acodec', 'pcm_f32le', '-f', 'wav', '-']
		if song.codec() not in set(["mp3", "aac"]) or (song.bitrate()>=310):
			avconv=subprocess.Popen(commandline, stdout=subprocess.PIPE)
			buffer=avconv.stdout.read(1024)
			AACenc=aacenc.AACenc(buffer, name +'.m4a', title=song.getTitle(),
                                 artist=song.getArtist(), albumArtist=song.getAlbumArtist(),
                                 genre=song.genre(), date=song.date(), track=song.getTrack(),
                                 disk=song.disc(), album=song.getAlbum())
			buffer=avconv.stdout.read(1024)
			while len(buffer):
				AACenc.write(buffer)
				buffer=avconv.stdout.read(1024)
			AACenc.closePIPE()
		else:
			avconv=subprocess.Popen(commandline, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
			avconv.communicate(bytes(ffmetadata, encoding="UTF-8"))
			avconv.wait()

	def convertPlaylist(tags, loading_baner):
		albums=set()
		for song in tags:
			if song.album() not in albums:
				albums.add(song.album())
				aldir=strtofile(song.album_artist())+' - '+strtofile(song.album())
				if not os.path.exists(os.path.join(outdir, aldir)):
					os.mkdir(os.path.join(outdir, aldir))
				if song.hasEmbededCover():
					streamer=ffmpeg_prober.getPPM_Stream(song.filename())
					resample(streamer.stdout, os.path.join(outdir, aldir, 'folder.jpg'), max=200)
				elif len(song.cover()):
					resample(song.cover(),
							 os.path.join(outdir, aldir, 'folder.jpg'),
							 max=200)
		loading_baner.set_ntracks(len(tags))
		loading_baner.update()
		for song in tags:
			convertAudio(song)
			loading_baner.increment()
			loading_baner.update()
		loading_baner.close()