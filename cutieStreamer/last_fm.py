#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime, time
import threading
from tkinter import Toplevel, Entry, messagebox, ttk
import pylast


LASTFM_API_KEY = "***INACTIVE***"
LASTFM_API_SECRET = "***INACTIVE***"


def getUnixTimestamp():
	return int(time.mktime(datetime.datetime.now().timetuple()))

def last_fm_scrobble(connection, track, timestamp):
	if track.getArtist() is not None and track.getTitle() is not None:
		tags = {
			'artist': track.getArtist(),
			'title': track.getTitle()
		}
		if track.getAlbum():
			tags['album']=track.getAlbum()
		if track.getAlbumArtist():
			tags['album_artist'] = track.getAlbumArtist()
		if track.getTrack():
			tags['track_number'] = track.getTrack()


class Last_fm_Scrobbler:
	def __init__(self, gui_object):
		self._connection = None
		self._current_track_start_playback = None
		self._current_track = None
		self._gui_object = gui_object

	def isConnected(self):
		return self._connection is not None

	def __getTags(self, track):
		if track.getArtist() is not None and \
				track.getTitle() is not None:
			tags = {
				'artist': track.getArtist(),
				'title': track.getTitle()
			}
			if track.getAlbum():
				tags['album']=track.getAlbum()
			if track.getAlbumArtist():
				tags['album_artist'] = track.getAlbumArtist()
			if track.getTrack():
				tags['track_number'] = track.getTrack()
			return tags
		else:
			raise ValueError
	
	def now_playing(self, track):
		if track is None:
			return None
		else:
			self._current_track = track
		if self.isConnected():
			try:
				tags = self.__getTags(track)
			except ValueError:
				pass
			else:
				self._connection.update_now_playing(**tags)
				self._gui_object.setScrobblingUpdateTimer()

	def scrobble(self, track):
		timestamp = getUnixTimestamp()
		if self._connection is not None and track != self._current_track:
			prev_track = self._current_track
			self._gui_object.cancelScrobblingUpdateTimer()
			self.now_playing(track)
			if prev_track is not None and (
					prev_track.duration() > 30 and
						(
							(timestamp-self._current_track_start_playback) >= prev_track.duration()/2 or
							(timestamp-self._current_track_start_playback) >= 4*60
						)
					):
				try:
					tags = self.__getTags(prev_track)
				except ValueError:
					pass
				else:
					self._connection.scrobble(
						timestamp=self._current_track_start_playback,
						duration=prev_track.duration(),
						**tags
					)
			self._current_track_start_playback = timestamp

	def __setConnection(self, connection):
		self._connection = connection
	
	def authorisation(self, root, guiObject):
		Last_fm_AuthorisationDialogue(root, guiObject, self.__setConnection)
	
	def loveThisTrack(self, track):
		pylast.Track(
			track.artist(),
			track.title(),
			self._connection
		).love()

class Last_fm_AuthorisationDialogue:
	def __init__(self, root, guiObject, setConnectionMethod):
		self.gui_object = guiObject
		self._setConnection = setConnectionMethod
		guiObject.freeze()
		self._root = Toplevel(root)
		ttk.Label(self._root, text='Login: ').grid(row=0, column=0, sticky='e')
		self._login_field = Entry(self._root)
		self._login_field.grid(row=0, column=1, columnspan=2)
		ttk.Label(self._root, text='Passwod: ').grid(row=1, column=0, sticky='e')
		self._password_field = Entry(self._root, show="*")
		self._password_field.grid(row=1, column=1, columnspan=2)
		ttk.Button(self._root, text="OK", command=self.__openConnection).grid(row=2, column=1)
		ttk.Button(self._root, text="Cancel", command=self.close).grid(row=2, column=2)
	def __openConnection(self):
		if self._login_field.get() and self._password_field.get():
			try:
				connection = pylast.LastFMNetwork(
					api_key=LASTFM_API_KEY,
					api_secret=LASTFM_API_SECRET,
					username=self._login_field.get(),
					password_hash=pylast.md5(self._password_field.get())
				)
			except pylast.WSError as e:
				messagebox.showerror('pylast.WSError', e.details)
			except Exception as e:
				raise e
			else:
				self._setConnection(connection)
				self.gui_object.lastfm_connection_active()
				self.close()
		elif self._login_field.get():
			messagebox.showerror('Last.fm authorisation', 'Enter password for log in')
		else:
			messagebox.showerror('Last.fm authorisation', 'Enter username and password for log in')
	def close(self):
		self.gui_object.unfreeze()
		self._root.destroy()