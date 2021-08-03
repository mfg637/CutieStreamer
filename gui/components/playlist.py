#!/usr/bin/python3
# -*- coding: utf-8 -*-
#Playlist GUI by mfg637

import os, sys, ffmpeg_prober, threading, io
from tkinter import PhotoImage, Frame, Label, Frame, Listbox, END, Widget
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from .ScrolledFrame import VerticalScrolledFrame
from abc import ABCMeta, abstractmethod
from audiolib import timecode
import subprocess
from platform import system

if system()=='Windows':
	status_info = subprocess.STARTUPINFO()
	status_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW

curdir=os.path.dirname(sys.argv[0])

class TrackListbox(Listbox):
    def __init__(self, master, callback, look_call, offset=0, cnf={}, **kw):
        Listbox.__init__(self, master, cnf, **kw)
        self._offset=offset
        self._callback=callback
        self._look_call= look_call
        self.bind("<Button-1>", self.__select_track)
        self.bind("<Double-Button-1>", self.__start_playing)
        self.bind("<Left>", lambda e: self.xview_moveto(0))
        self.bind("<Right>", lambda e: self.xview_moveto(0))
        self._selected_track = -1

    def __start_playing(self, event):
        self._callback(self._offset + self.curselection()[0])

    def __select_track(self, event):
        self._look_call()
        try:
            if self._selected_track == -2:
                self._selected_track = self.curselection()[0]
                self.__start_playing(event)
            elif self._selected_track == -1:
                self._selected_track = -2
            elif self._selected_track != self.curselection()[0]:
                self._selected_track = self.curselection()[0]
            else:
                self.__start_playing(event)
        except IndexError:
            self._selected_track = -2

    def last_track(self):
        return self._offset+self.size()-1

    def activate_track(self, track):
        self._selected_track = -1
        self.activate(track-self._offset)
        self.focus()

class StubListbox(Listbox):
    def __init__(self, master, cnf={}, **kw):
        Listbox.__init__(self, master, cnf, **kw)
        self.insert(0, "Playlist is empty")

class FrameWrappedWidget:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, master=None):
        self._wrapper = Widget(master, '')

    def pack(self, **kw):
        self._wrapper.pack(**kw)

    def grid(self, **kw):
        self._wrapper.grid(**kw)

class AlbumGroup(FrameWrappedWidget):
    def __init__(
            self,
            parent,
            tag,
            callback,
            async_cover_loading=True,
            cover_thumbnail=None
        ):
        self._tracks=[]
        self._tracks.append(tag)
        self._wrapper = Frame(parent)
        self._cover_thumbnail=None
        self._cover_thumb_img = None
        self._album = tag.get_tags_list().album()
        self._album_artist = tag.get_tags_list().album_artist()
        self._callback=callback
        self._wrapper.bind("<Button-1>", self.__edit_tags)
        if tag.cover()!='':
            self._cover_label=Label(self._wrapper)
            self._cover_label.grid(row=0, column=0, rowspan=2)
            self._cover_label.bind("<Button-1>", self.__edit_tags)
            if async_cover_loading:
                thread=threading.Thread(target=self.__createCoverThumbnail, args=(tag, cover_thumbnail))
                thread.start()
            else:
                self.__createCoverThumbnail(tag, cover_thumbnail)
        album_label = Label(self._wrapper, text=tag.get_tags_list().album()[:44])
        album_label.grid(row=0, column=1, sticky='w')
        album_label.bind("<Button-1>", self.__edit_tags)
        artist_label = Label(self._wrapper, text='by '+tag.get_tags_list().album_artist()[:40])
        artist_label.grid(row=1, column=1, sticky='w')
        artist_label.bind("<Button-1>", self.__edit_tags)

    def __decode_webp(self, rawbytes):
        commandline = [
            os.path.join(os.path.dirname(sys.argv[0]), 'dwebp'),
            '-o', '-', '--', '-', '-quiet'
        ]
        if system()=='Windows':
            process = subprocess.Popen(
                commandline, stdin=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=status_info
            )
        else:
            process = subprocess.Popen(commandline, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        process.stdin.write(rawbytes)
        process.stdin.close()
        outbuf = process.stdout.read()
        process.terminate()
        return io.BytesIO(outbuf)

    def __createCoverThumbnail(self, tag, image=None):
        if image is not None:
            try:
                buf = io.BytesIO(image)
                self._cover_thumbnail=ImageTk.PhotoImage(Image.open(buf))
            except OSError:
                buf = self.__decode_webp(image)
                self._cover_thumbnail=ImageTk.PhotoImage(Image.open(buf))
            del buf
        else:
            self._cover_thumbnail=ImageTk.PhotoImage(tag.get_front_cover_image((40, 40), force=True))
        self._cover_label['image'] = self._cover_thumbnail

    def get_thumbnail_image(self):
        return self._cover_thumb_img

    def __edit_tags(self, event):
        self._callback(self._album, self._album_artist, self._tracks)

    def append_track(self, tag):
        self._tracks.append(tag)


class PlaylistWidget(FrameWrappedWidget):
    def __init__(self, master, **kw):
        self._wrapper = VerticalScrolledFrame(master)
        self.playlist_config=kw
        self._albumGroupList=[]
        self._playlistbox_items=[]
        StubListbox(self._wrapper.interior, **kw).grid(row=0,column=0)
        self._active_track=-1
        self._k=0
        self._delay = 0

    def __add_tracks(
        self,
        tracks,
        playlist_callback,
        album_group_callback,
        track_offset,
        async_cover_loading=True,
        cover_thumbnails=None
    ):
        current_album_artist = None
        current_album = None
        k = self._k
        tracklist = Listbox(self._wrapper.interior)
        albumGroupItem = None
        for track in tracks:
            tags = track.get_tags_list()
            if tags.album() != current_album or \
                    tags.album_artist() != current_album_artist:
                if cover_thumbnails is not None and len(cover_thumbnails) and track.cover() != "":
                    albumGroupItem = AlbumGroup(
                        self._wrapper.interior,
                        track, album_group_callback,
                        async_cover_loading,
                        cover_thumbnails.pop(0)
                    )
                else:
                    albumGroupItem = AlbumGroup(
                        self._wrapper.interior,
                        track, album_group_callback,
                        async_cover_loading
                    )
                self._albumGroupList.append(albumGroupItem)
                albumGroupItem.grid(row=k, column=0, sticky='w')
                k += 1
                tracklist = TrackListbox(
                    self._wrapper.interior,
                    playlist_callback,
                    self.__look_playlist,
                    track_offset,
                    **self.playlist_config
                )
                tracklist.grid(row=k, column=0)
                self._playlistbox_items.append(tracklist)
                k += 1
                current_album = tags.album()
                current_album_artist = tags.album_artist()
            else:
                albumGroupItem.append_track(track)
            if tags.disc() is not None:
                track_repr = tags.disc()
            else:
                track_repr = ''
            track_repr += "{} {}".format(tags.track(), tags.title())
            if (tags.getArtist() is not None) and (tags.getArtist()!=current_album_artist):
                track_repr += " - {}".format(tags.getArtist())
            track_repr += " [{}]".format(timecode.encode(int(round(track.duration()))))
            tracklist.insert(END, track_repr)
            track_offset += 1
        self._k = k

    def playlist_initiation(self, tags, playlist_callback, albumGroupCallback,
        async_cover_loading=True, cover_thumbnails=None):
        self._albumGroupList.clear()
        self._playlistbox_items.clear()
        for widget in self._wrapper.interior.winfo_children():
            widget.destroy()
        self._wrapper.canvas.yview_moveto(0)
        track_offset = 0
        self._k = 0
        self.__add_tracks(
            tags,
            playlist_callback,
            albumGroupCallback,
            track_offset,
            async_cover_loading,
            cover_thumbnails
        )

    def activate(self, track):
        if self._delay>0:
            self._delay -=1
        else:
            i=0
            while (i<len(self._playlistbox_items) and \
                self._playlistbox_items[i].last_track()<track):
                i+=1
            self._playlistbox_items[i].activate_track(track)

    def clear(self):
        self._albumGroupList.clear()
        self._playlistbox_items.clear()
        for widget in self._wrapper.interior.winfo_children():
            widget.destroy()
        self._wrapper.canvas.yview_moveto(0)
        StubListbox(self._wrapper.interior, **self.playlist_config).grid(row=0,column=0)

    def append(self, tags, playlist_callback, albumGroupCallback):
        track_offset = self._playlistbox_items[-1].last_track()+1
        self.__add_tracks(
            tags[track_offset:],
            playlist_callback,
            albumGroupCallback,
            track_offset
        )

    def getCoverThumbnails(self):
        thumbnails = []
        for i in self._albumGroupList:
            if i.get_thumbnail_image() is not None:
                thumbnails.append(i.get_thumbnail_image())
        return thumbnails
    
    def __look_playlist(self, event=None):
        self._delay = 5