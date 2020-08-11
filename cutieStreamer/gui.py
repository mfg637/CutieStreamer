#!/usr/bin/python3
# -*- coding: utf-8 -*-
# gui by mfg637

import exceptions
import os
import sys
import threading
from platform import system
import pynput

LAST_FM = None
#try:
#	import pylast
#except ImportError:
#	LAST_FM = False
#else:
#	LAST_FM = True
#	from . import last_fm
from tkinter import Tk, PhotoImage, Menu, DISABLED, Frame, Label, HORIZONTAL, NORMAL
from tkinter import ttk, filedialog, messagebox
from audiolib import tagIndexer
from . import playlist
from PIL import Image, ImageTk
import gui
import converter


support_soundfiles_extensions = ("*.wav *.mp3 *.m4a *.flac *.ogg *.opus"
								"*.ape *.tak *.tta *wv *mka")


class GUI:
	def __init__(self, _playlist, async_playlist_load=True):
		if _playlist is not None and \
			isinstance(_playlist, playlist.Playlist):
			self._playlist=_playlist
			self._playlist.setGui(self)
		else:
			self._playlist = None
		self._root=Tk()
		self._root.title("CutieStreamer")
		curdir=os.path.dirname(sys.argv[0])
		gui.components.init(curdir)
		if system()=='Windows':
			self._root.iconbitmap(os.path.join(os.path.dirname(sys.argv[0]),
			'images', 'favicon.ico'))
		else:
			icon_sizes = ("16", "24", "32", "48", "256")
			icon_extensions = ["gif"] * 3 + ["png"] * 2
			icons = [
				PhotoImage(file=os.path.join(
					os.path.dirname(sys.argv[0]), 'images', 'favicon{}.{}'.format(icon_sizes[i], icon_extensions[i])
				)) for i in range(5)
			]
			self._root.wm_iconphoto(True, *icons)
		self._playing_timer = None
		self._loading_banner_img_PILobj=Image.open(os.path.join(curdir, 'images',
			"loading_banner.png"))
		self._loading_banner_img=ImageTk.PhotoImage(self._loading_banner_img_PILobj)
		self.loading_banner = None
		self.playback_mode=0
		self.plmd=0
		self._trackPropertiesFrame=None
		if LAST_FM:
			self.last_fm = last_fm.Last_fm_Scrobbler(self)
		self._last_fm_scrobbling_update_timer = None

		self._inf_labels = gui.components.TrackInfo(self._root, width=320)
		self._inf_labels.grid(row=0, column=0, sticky='w')

		self._playback_controls = Frame(self._root)
		self._timecode_label = Label(self._playback_controls)
		self._timecode_label.pack(side="left")
		self._prev_btn = gui.components.PreviousTrackButton(
			self._playback_controls,
			self._timeline_ready,
			self.__prev_track_change
		)
		self._prev_btn.pack(side='left')
		self._playpause_btn = gui.components.PlayPauseButton(
			self._playback_controls,
			self._timeline_ready,
			self._togle_play_state
		)
		self._playpause_btn.pack(side='left')
		self._next_btn = gui.components.NextTrackButton(
			self._playback_controls,
			self._timeline_ready,
			self.__next_track_change
		)
		self._next_btn.pack(side='left')
		self._duration_label = Label(self._playback_controls)
		self._duration_label.pack(side="left")
		self._playback_controls.grid(row=1, column=0)

		self._menubar = Menu(self._root)

		self._filemenu = Menu(self._menubar, tearoff=0)
		self._filemenu.add_command(label="Show properties", command=self.__showPropertiesFrame)
		#self._filemenu.add_command(label="Synchronise to mobile", command=self.__runAlbumSync)
		self._filemenu.add_command(label="Exit", command=self._root.quit)
		self._menubar.add_cascade(label="File", menu=self._filemenu)

		self._playback_menu = Menu(self._menubar, tearoff=0)
		self._playpause_btn.bind_menu_item(self._playback_menu, 0)
		self._playback_menu.add_command(label="Stop", command=self._stop, state=DISABLED)
		self._prev_btn.bind_menu_item(self._playback_menu, 2)
		self._next_btn.bind_menu_item(self._playback_menu, 3)
		self._playback_menu.add_separator()

		self._playback_menu.add_checkbutton(label="gapless playback",
			command=self.setGaplessMode, state=(NORMAL if self._playlist is not None else DISABLED),
			onvalue=0, variable=self.plmd)
		self._playback_menu.add_checkbutton(label="crossfade playback",
			command=self.setCrossfadeMode, state=(NORMAL if self._playlist is not None else DISABLED),
			onvalue=1, variable=self.plmd)
		self._menubar.add_cascade(label="Playback", menu=self._playback_menu)

		self._playlist_menu = Menu(self._menubar, tearoff=0)
		self._playlist_menu.add_command(label="Create playlist",
			command=self._playlist_creator)
		self._playlist_menu.add_command(label="Scan directory in new playlist",
			command=self._scandir)
		self._playlist_menu.add_command(label="Add files to current playlist",
			command=self._add_track_in_playlist, state=DISABLED)
		self._playlist_menu.add_command(label="Scan directory to current playlist",
			command=self._addDirectoryToPlaylist, state=DISABLED)
		self._playlist_menu.add_separator()
		self._playlist_menu.add_command(label="Open playlist",
			command=self.__open_playlist)
		self._playlist_menu.add_command(label="Save playlist",
			command=self.__save_playlist, state=DISABLED)
		self._menubar.add_cascade(label="Playlist", menu=self._playlist_menu)

		if LAST_FM:
			self._last_fm_menu = Menu(self._menubar, tearoff=0)
			self._last_fm_menu.add_command(label="login", command=self.__last_fm_open_connection)
			self._last_fm_menu.add_command(label="love this track", command=self.__lastfm_add_to_favs)
			self._menubar.add_cascade(label="Last.fm", menu=self._last_fm_menu)

		self._root.config(menu=self._menubar)

		timeline_kwargs = {"orient": HORIZONTAL, "showvalue": 0, "sliderlength": 10}
		if system()=="Windows":
			timeline_kwargs["length"] = 310
		else:
			timeline_kwargs["length"] = 340

		self._timeline = gui.components.TimeLine(
			self._root,
			self._timecode_label,
			self._duration_label,
			self._timeline_ready,
			self._timeline_seek,
			**timeline_kwargs
		)

		self._timeline.grid(row=2, column=0)

		if system()=="Windows":
			self._playlist_box = gui.components.playlist.PlaylistWidget(self._root, width=48, height=0)
		else:
			self._playlist_box = gui.components.playlist.PlaylistWidget(self._root, width=40, height=0)
		if _playlist is not None and \
			(type(_playlist) is playlist.Playlist or type(_playlist) is playlist.DeserialisedPlaylist):
			self._playlist_box.playlist_initiation(
				_playlist.tags, self.select_item, self.openAlbumDialogue, async_playlist_load
			)
		self._playlist_box.grid(row=3, column=0)

		self._playlist_controls = Frame(self._root)
		self._playlist_controls.grid(row=4, column=0)
		self._create_playlist_btn = ttk.Button(self._playlist_controls, text='New playlist',
			command=self._playlist_creator)
		self._create_playlist_btn.pack(side='left')
		self._index_dir_btn = ttk.Button(self._playlist_controls, text='Index dir',
			command=self._scandir)
		self._index_dir_btn.pack(side='left')
		self._add_tracks_btn = ttk.Button(self._playlist_controls, text='Add tracks',
			command=self._add_track_in_playlist)
		self._add_tracks_btn.pack(side='left')
		self._add_dir_btn = ttk.Button(self._playlist_controls, text='Add directory',
			command=self._addDirectoryToPlaylist)
		self._add_dir_btn.pack(side='left')

		self._status_bar = Frame(self._root)
		self._codec_label = Label(self._status_bar)
		self._codec_label.pack(side="left")
		self._bitrade_label = Label(self._status_bar)
		self._bitrade_label.pack(side="left")
		self._playstate_label = Label(self._status_bar)
		self._playstate_label.pack(side="left")
		if LAST_FM:
			self._lastfm_conection_label = Label(self._status_bar)
			self._lastfm_conection_label.pack(side="left")
		self._status_bar.grid(row=5, column=0, sticky='w')

		if _playlist is not None and \
			isinstance(_playlist, playlist.Playlist):
			self.__unlock_playback_controls()
		elif (_playlist is not None) and (type(_playlist) is str):
			playlist.deserizlize_playlist_file(_playlist, self)
			self.__unlock_playback_controls()
		else:
			self.__lock_playback_controls()

		self._root.protocol("WM_DELETE_WINDOW", self.quit)
		self._root.bind("<space>", self._togle_play_state)
		self._root.bind("<Left>", self.__seek_back)
		self._root.bind("<Right>", self.__seek_forward)
		self._keyboard_listener = pynput.keyboard.Listener(on_press=self.pynput_global_key_listener)
		self._keyboard_listener.start()

		self._root.mainloop()


	def _togle_play_state(self):
		if self._playlist.isPlaying():
			self._playlist.pause()
			self._playstate_label['text'] = 'playback stoped'
			self._playpause_btn.setPlay()
			self.__lock_prev_next_buttons()
			self._root.after_cancel(self._playing_timer)
			self.cancelScrobblingUpdateTimer()
		else:
			self._playlist.play()
			self._playpause_btn.setPause()
			self._playback_menu.entryconfig(1, state=NORMAL)
			self._current_track_number = self._playlist.currentPosition()['track']
			if LAST_FM and self.last_fm.isConnected():
				lfm_thread=threading.Thread(
					target=self.last_fm.now_playing,
					args=(self._playlist.tags[self._current_track_number],)
				)
				lfm_thread.start()
			self._playing_update()


	def _stop(self, event=None):
		self._playlist.stop()
		self._playpause_btn.setPlay()
		self._playstate_label['text'] = 'playback stoped'
		self.__lock_prev_next_buttons()
		self._root.after_cancel(self._playing_timer)
		self.cancelScrobblingUpdateTimer()
		self._timeline.reset()
		self._playback_menu.entryconfig(1, state=DISABLED)


	def select_item(self, track):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		self._playlist.PlayFromItem(track)
		self._playback_menu.entryconfig(1, state=NORMAL)
		if LAST_FM and self.last_fm.isConnected():
			Position = self._playlist.currentPosition()
			lfm_scroble_thread = threading.Thread(
				target = self.last_fm.scrobble,
				args = (
					self._playlist.tags[Position['track']],
				)
			)
			lfm_scroble_thread.start()
		self._playing_update()
		self._playpause_btn.setPause()


	def _playing_update(self):
		if not self._playlist.isEnd():
			self._playpause_btn.setPause()
			self._playing_timer = self._root.after(100, self._playing_update)
			Position=self._playlist.currentPosition()
			if Position['track']>0:
				self._prev_btn.enable()
			else:
				self._prev_btn.disable()
			if Position['track'] < (self._playlist.get_playlist_len() - 1):
				self._next_btn.enable()
			else:
				self._next_btn.disable()
			tag = self._playlist.tags[Position['track']]
			self._timeline.update_track_position(Position, tag)
			self._playlist_box.activate(Position['track'])
			self._inf_labels.update_track(tag)
			self._codec_label['text'] = self._playlist.tags[Position['track']].codec().upper()
			self._bitrade_label['text'] = str(
				int(self._playlist.tags[Position['track']].bitrate()))+'kbps'
			self._playstate_label['text'] = self._playlist.playback_mode+' playback'
			if LAST_FM and self.last_fm.isConnected():
				lfm_scroble_thread = threading.Thread(
					target = self.last_fm.scrobble,
					args = (
						self._playlist.tags[Position['track']],
					)
				)
				lfm_scroble_thread.start()
		else:
			self._playpause_btn.setReplay()
			if LAST_FM and self.last_fm.isConnected():
				lfm_scroble_thread = threading.Thread(
					target = self.last_fm.scrobble,
					args = (
						None,
					)
				)
				lfm_scroble_thread.start()


	def _timeline_ready(self):
		self._root.after_cancel(self._playing_timer)


	def _timeline_seek(self, position: float):
		self._playlist.seek(position)
		self._playing_timer = self._root.after(100, self._playing_update)
		self._playpause_btn.setPause()


	def _playlist_creator(self):
		self.display_loading_banner(True)
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		self._timeline.reset()
		filelist = filedialog.askopenfilenames(parent=self.loading_banner.root,
			title="select sound files",
			filetypes=(("sound files", support_soundfiles_extensions),
			("index files", "*.cue"),
			("Winamp playlist", "*.m3u *.m3u8"),
			("all files", "*.*"))
		)
		if len(filelist)>0:
			try:
				self.loading_banner.progressbar['maximum'] = len(filelist)
				if self._playlist is not None:
					self._playlist.clear()
					del self._playlist
				self._playlist = playlist.Playlist(filelist, progressbar = self.loading_banner.progressbar)
				self._playlist.setGui(self)
				if self.playback_mode==0:
					self._playlist.playback_mode='gapless'
				elif self.playback_mode==1:
					self._playlist.playback_mode='crossfade'
				self.__unlock_playback_controls()
				self._playlist_box.playlist_initiation(
					self._playlist.tags, self.select_item, self.openAlbumDialogue
				)
			except tagIndexer.CUEparserError as e:
				messagebox.showerror('CUEindexer', 'Error at line:\n'+
					e.line+e.message)
			except exceptions.invalidFilename as e:
				messagebox.showerror('FileIndexer', 'invalid filename:\n'+
					ascii(e.filename))
				self._playlist=None
				self.clear()
			self._playpause_btn.setPlay()
			self._playstate_label['text'] = 'playback stoped'
			self.__lock_prev_next_buttons()
		elif self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
		self.hide_loading_banner()


	def _add_track_in_playlist(self):
		self.display_loading_banner(True)
		self.freeze()
		filelist = filedialog.askopenfilenames(parent=self.loading_banner.root,
			title="select sound files",
			filetypes=(("sound files", support_soundfiles_extensions),
				("index files", "*.cue"),
				("all files", "*.*")))
		if len(filelist):
			self.loading_banner.progressbar['maximum'] = len(filelist)
			try:
				self._playlist.addFiles(filelist, progressbar = self.loading_banner.progressbar)
			except tagIndexer.CUEparserError as e:
				messagebox.showerror('CUEindexer', 'Error at line:\n'+
					e.line+e.message)
			except exceptions.invalidFilename as e:
				messagebox.showerror('FileIndexer', 'invalid filename:\n'+
					ascii(e.filename))
				self._playlist=None
				self.clear()
			else:
				self._playlist_box.append(self._playlist.tags, self.select_item, self.openAlbumDialogue)
				if self._playlist.state():
					self._playing_update()
		elif self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
		self.hide_loading_banner()


	def _addDirectoryToPlaylist(self):
		self.display_loading_banner(True)
		self.freeze()
		directory = filedialog.askdirectory(parent=self.loading_banner.root,
			title="select music folder")
		if directory:
			try:
				self._playlist.addFiles(tagIndexer.folder_indexer(directory,
										progressbar = self.loading_banner.progressbar))
			except tagIndexer.CUEparserError as e:
				messagebox.showerror('CUEindexer', 'Error at line:\n'+
					e.line+e.message)
			else:
				self._playlist_box.append(self._playlist.tags, self.select_item, self.openAlbumDialogue)
				if self._playlist.state():
					self._playing_update()
			self._playpause_btn.setPlay()
			self._playstate_label['text'] = 'playback stoped'
		elif self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
		self.hide_loading_banner()


	def _scandir(self):
		self.display_loading_banner(True)
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		directory = filedialog.askdirectory(parent=self.loading_banner.root,
			title="select music folder")
		if len(directory):
			if self._playlist is not None:
				self._playlist.clear()
				del self._playlist
			try:
				self._playlist = playlist.Playlist(tagIndexer.folder_indexer(directory,
													progressbar = self.loading_banner.progressbar))
				self._playlist.setGui(self)
				if self.playback_mode==0:
					self._playlist.playback_mode='gapless'
				elif self.playback_mode==1:
					self._playlist.playback_mode='crossfade'
			except tagIndexer.CUEparserError as e:
				messagebox.showerror('CUEindexer', 'Error at line:\n'+
					e.line+e.message)
			else:
				self.__unlock_playback_controls()
				self._playlist_box.playlist_initiation(
					self._playlist.tags, self.select_item, self.openAlbumDialogue
				)
				self._playpause_btn.setPlay()
				self._playstate_label['text'] = 'playback stoped'
				self.__lock_prev_next_buttons()
		elif self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
		self.hide_loading_banner()


	def __prev_track_change(self):
		Position = self._playlist.currentPosition()
		if not self._playlist.isStart():
			if self._playing_timer is not None:
				self._root.after_cancel(self._playing_timer)
			prev_track = Position['track']-1
			self._playlist.PlayFromItem(prev_track)
			if prev_track == 0:
				self._prev_btn.disable()
		if LAST_FM and self.last_fm.isConnected():
			lfm_scroble_thread = threading.Thread(
				target = self.last_fm.scrobble,
				args = (
					self._playlist.tags[Position['track']],
				)
			)
			lfm_scroble_thread.start()
		self._playing_update()


	def __next_track_change(self):
		Position = self._playlist.currentPosition()
		if not self._playlist.isEnd():
			if self._playing_timer is not None:
				self._root.after_cancel(self._playing_timer)
			next_track = Position['track']+1
			self._playlist.PlayFromItem(next_track)
			if next_track < (self._playlist.get_playlist_len() -1):
				self._next_btn.enable()
			else:
				self._next_btn.disable()
		if LAST_FM and self.last_fm.isConnected():
			lfm_scroble_thread = threading.Thread(
				target = self.last_fm.scrobble,
				args = (
					self._playlist.tags[Position['track']],
				)
			)
			lfm_scroble_thread.start()
		self._playing_update()


	def __lock_playback_controls(self):
		self._playpause_btn.disable()
		self._add_tracks_btn['state']='disabled'
		self._add_dir_btn['state']='disabled'
		self._prev_btn.disable()
		self._next_btn.disable()
		self._playback_menu.entryconfig(1, state=DISABLED)


	def __unlock_playback_controls(self):
		self._playpause_btn.enable()
		self._add_tracks_btn['state']='normal'
		self._add_dir_btn['state']='normal'
		self._playback_menu.entryconfig(5, state=NORMAL)
		self._playback_menu.entryconfig(6, state=NORMAL)
		self._playlist_menu.entryconfig(2, state=NORMAL)
		self._playlist_menu.entryconfig(3, state=NORMAL)
		self._playlist_menu.entryconfig(6, state=NORMAL)


	def display_loading_banner(self, window_raise=False):
		self.loading_banner = gui.dialogues.LoadingBanner(
			self._root,
			self._loading_banner_img,
			window_raise
		)


	def hide_loading_banner(self):
		del self.loading_banner


	def setGaplessMode(self):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		self._playlist.change_playback_mode('gapless')
		if self._playlist.state():
			self._playing_update()
		self.playback_mode=0


	def setCrossfadeMode(self):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		self._playlist.change_playback_mode('crossfade')
		if self._playlist.state():
			self._playing_update()
		self.playback_mode=1


	def __lock_prev_next_buttons(self):
		self._prev_btn.disable()
		self._next_btn.disable()


	def quit(self):
		if self._playlist is not None:
			self._playlist.clear()
			del self._playlist
		self._keyboard_listener.stop()
		self._root.destroy()


	def __save_playlist(self):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
		filename=filedialog.asksaveasfilename(title = "save playlist",
			filetypes = (("playlist", "*.cspl"),("json","*.cutieStreamer.json")),
			defaultextension=".cspl")
		if filename:
			if filename[-5:]==".cspl":
				playlist.serizlize_playlist_file(filename, self._playlist, self)
			else:
				self._playlist.serialize(filename)
		if self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
	

	def setPlaylist(self, _playlist, cover_thumbnails):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
			self._timeline.reset()
		if self._playlist is not None:
			self._playlist.clear()
			del self._playlist
		self._playlist = _playlist
		self._playlist.setGui(self)
		if self.playback_mode==0:
			self._playlist.playback_mode='gapless'
		elif self.playback_mode==1:
			self._playlist.playback_mode='crossfade'
		self.__unlock_playback_controls()
		self._playlist_box.playlist_initiation(
			self._playlist.tags,
			self.select_item,
			self.openAlbumDialogue,
			cover_thumbnails = cover_thumbnails
		)
		self._playpause_btn.setPlay()
		self._playstate_label['text'] = 'playback stoped'
		self.__lock_prev_next_buttons()

	def __open_playlist(self):
		self.display_loading_banner(True)
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
			self._timeline.reset()
		filename = filedialog.askopenfilename(parent=self.loading_banner.root,
			title="select playlist",
			filetypes=(("playlist formts", "*.cspl *.cutieStreamer.json"),
			("playlist file", "*.cspl"),
			("json", "*.cutieStreamer.json"),
			("all files", "*.*"))
		)
		if len(filename)>0:
			if filename[-19:]=='.cutieStreamer.json':
				if self._playlist is not None:
					self._playlist.clear()
					del self._playlist
				self._playlist = playlist.DeserialisedPlaylist(filename)
				self._playlist.setGui(self)
				if self.playback_mode==0:
					self._playlist.playback_mode='gapless'
				elif self.playback_mode==1:
					self._playlist.playback_mode='crossfade'
				self.__unlock_playback_controls()
				self._playlist_box.playlist_initiation(
					self._playlist.tags, self.select_item, self.openAlbumDialogue
				)
				self._playpause_btn.setPlay()
				self._playstate_label['text'] = 'playback stoped'
				self.__lock_prev_next_buttons()
			elif filename[-5:]=='.cspl':
				playlist.deserizlize_playlist_file(filename,self)
		elif self._playlist is not None:
			self._playing_update()
		self.hide_loading_banner()


	def __showPropertiesFrame(self):
		if self._playlist.isPlaying():
			Position=self._playlist.currentPosition()
			self._trackPropertiesFrame = gui.dialogues.TrackProperties(self._root,
				self._playlist.tags[Position['track']], self)
		else:
			messagebox.showerror('DisplayProperties',
									'Can`t display track properties: nothing is playing')


	def clear(self):
		self._playlist_box.clear()
		if self._playlist is not None:
			self._playlist.clear()
		self._playlist = None
		self._playpause_btn.disable()
		self._add_tracks_btn['state']='disabled'
		self._add_dir_btn['state']='disabled'
		self._prev_btn.disable()
		self._next_btn.disable()
		self._playback_menu.entryconfig(1, state=DISABLED)
		self._playback_menu.entryconfig(5, state=DISABLED)
		self._playback_menu.entryconfig(6, state=DISABLED)
		self._playlist_menu.entryconfig(2, state=DISABLED)
		self._playlist_menu.entryconfig(3, state=DISABLED)
		self._playlist_menu.entryconfig(6, state=DISABLED)
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
			self._timeline.reset()
		self._inf_labels.reset()
		self._codec_label['text'] = ''
		self._bitrade_label['text'] = ''
		self._playstate_label['text'] = ''


	def playlist_getCoverThumbnails(self):
		return self._playlist_box.getCoverThumbnails()


	def __last_fm_open_connection(self):
		if LAST_FM and not self.last_fm.isConnected():
			self.last_fm.authorisation(self._root, self)
	

	def __lastfm_add_to_favs(self):
		if LAST_FM and self.last_fm.isConnected():
			cp = self._playlist.currentPosition()['track']
			self.last_fm.loveThisTrack(self._playlist.tags[cp])


	def freeze(self):
		if self._playing_timer is not None:
			self._root.after_cancel(self._playing_timer)
	

	def unfreeze(self):
		if self._playlist is not None and self._playlist.isPlaying():
			self._playing_update()
	

	def lastfm_connection_active(self):
		self._lastfm_conection_label['text'] = 'Last.fm conection'

	def openAlbumDialogue(self, album, artist, tracks):
		self.freeze()
		gui.dialogues.AlbumDialogue(self._root, self, album, artist, tracks)
	
	def setAlbumTags(self, tracks, new_album_artist, new_album, disc=None):
		self._playlist.setAlbumArtistTags(tracks, new_album_artist, new_album, disc)
		self.playlist_update()
	
	def playlist_update(self):
		self._playlist_box.playlist_initiation(
			self._playlist.tags, self.select_item, self.openAlbumDialogue, True
		)
	
	def convertAlbum(self, tracks):
		self.freeze()
		converter.outdir = filedialog.askdirectory(parent=self._root,
										title="select output folder")
		self.unfreeze()
		if not converter.outdir:
			return None
		convert_thread = threading.Thread(
			target = converter.convertPlaylist,
			args = (tracks, gui.dialogues.ConvertProgress(self._root))
		)
		convert_thread.start()

	def setScrobblingUpdateTimer(self):
		self._last_fm_scrobbling_update_timer = self._root.after(30000, self.scrobblingUpdateEvent)

	def cancelScrobblingUpdateTimer(self):
		if self._last_fm_scrobbling_update_timer is not None:
			self._root.after_cancel(self._last_fm_scrobbling_update_timer)
	
	def scrobblingUpdateEvent(self):
		if LAST_FM and self.last_fm.isConnected():
			current_track = self._playlist.currentPosition()['track']
			lfm_thread=threading.Thread(
				target=self.last_fm.now_playing,
				args=(self._playlist.tags[current_track],)
			)
			lfm_thread.start()
	
	def __seek_back(self, event):
		if self._playlist.isPlaying():
			self._root.after_cancel(self._playing_timer)
			time = self._playlist.currentPosition()['time']
			self._playlist.seek(time-10)
			self._playing_timer = self._root.after(100, self._playing_update)
			self._playpause_btn.setPause()

	def __seek_forward(self, event):
		if self._playlist.isPlaying():
			self._root.after_cancel(self._playing_timer)
			time = self._playlist.currentPosition()['time']
			self._playlist.seek(time+10)
			self._playing_timer = self._root.after(100, self._playing_update)
			self._playpause_btn.setPause()

	def pynput_global_key_listener(self, key):
		if self._playlist is not None:
			position = self._playlist.currentPosition()
			if key == pynput.keyboard.KeyCode(vk=269025044) or key == pynput.keyboard.KeyCode(vk=269025073):
				self._togle_play_state()
			elif key == pynput.keyboard.KeyCode(vk=269025046):
				if position['time']>15:
					self._playlist.seek(0)
				elif (position['track']-1) >= 0:
					self.__prev_track_change()
			elif key == pynput.keyboard.KeyCode(vk=269025047) and \
				(position['track'] + 1) < self._playlist.get_playlist_len():
				self.__next_track_change()
			elif key == pynput.keyboard.KeyCode(vk=269025045):
				self._stop()
