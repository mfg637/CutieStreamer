#!/usr/bin/python3
# -*- coding: utf-8 -*-
# gui by mfg637


from tkinter import Tk, PhotoImage, Menu, DISABLED, Frame, Label, HORIZONTAL, NORMAL
from tkinter import ttk, filedialog, messagebox
from audiolib import tagIndexer
from . import playlist
from .playlist import PlaybackModeEnum
from audiolib.enums import GainModeEnum
from PIL import Image, ImageTk
from platform import system

import logging
import custom_exceptions
import os
import sys
import threading
import pynput

import gui
import converter

logger = logging.getLogger(__name__)

support_sound_files_extensions = "*.wav *.mp3 *.m4a *.flac *.ogg *.opus *.ape *.tak *.tta *wv *mka"


class GUI:
    def __init__(self, _playlist, async_playlist_load=True):
        if _playlist is not None and \
                isinstance(_playlist, playlist.Playlist):
            self._playlist = _playlist
            self._playlist.set_gui(self)
        else:
            self._playlist = None
        self._root = Tk()
        self._root.title("CutieStreamer")
        curdir = os.path.dirname(sys.argv[0])
        gui.components.init(curdir)
        if system() == 'Windows':
            self._root.iconbitmap(
                os.path.join(
                    os.path.dirname(sys.argv[0]),
                    'images',
                    'favicon.ico'
                )
            )
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
        self._loading_banner_img_PILobj = Image.open(
            os.path.join(
                curdir,
                'images',
                "loading_banner.png"
            )
        )
        self._loading_banner_img = ImageTk.PhotoImage(self._loading_banner_img_PILobj)
        self.loading_banner = None
        self.playback_mode = PlaybackModeEnum.GAPLESS
        self.gain_mode = GainModeEnum.NONE
        self._trackPropertiesFrame = None

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
            self._toggle_play_state
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
        self._filemenu.add_command(label="Show properties", command=self.__show_properties_frame)
        self._filemenu.add_command(label="Exit", command=self._root.quit)
        self._menubar.add_cascade(label="File", menu=self._filemenu)

        self._playback_menu = Menu(self._menubar, tearoff=0)
        self._playpause_btn.bind_menu_item(self._playback_menu, 0)
        self._playback_menu.add_command(label="Stop", command=self._stop, state=DISABLED)
        self._prev_btn.bind_menu_item(self._playback_menu, 2)
        self._next_btn.bind_menu_item(self._playback_menu, 3)
        self._playback_menu.add_separator()

        self._playback_menu.add_checkbutton(
            label="gapless playback",
            command=self.set_gapless_mode,
            state=(NORMAL if self._playlist is not None else DISABLED),
            onvalue=PlaybackModeEnum.GAPLESS.value,
            variable=self.playback_mode.value
        )
        self._playback_menu.add_checkbutton(
            label="crossfade playback",
            command=self.set_crossfade_mode,
            state=(NORMAL if self._playlist is not None else DISABLED),
            onvalue=PlaybackModeEnum.CROSSFADE.value,
            variable=self.playback_mode.value
        )
        self._menubar.add_cascade(label="Playback", menu=self._playback_menu)

        self._playlist_menu = Menu(self._menubar, tearoff=0)
        self._playlist_menu.add_command(
            label="Create playlist",
            command=self._playlist_creator
        )
        self._playlist_menu.add_command(
            label="Scan directory in new playlist",
            command=self._scan_dir
        )
        self._playlist_menu.add_command(
            label="Add files to current playlist",
            command=self._add_track_in_playlist, state=DISABLED
        )
        self._playlist_menu.add_command(
            label="Scan directory to current playlist",
            command=self._add_directory_to_playlist,
            state=DISABLED
        )
        self._playlist_menu.add_separator()
        self._playlist_menu.add_command(
            label="Open playlist",
            command=self.__open_playlist
        )
        self._playlist_menu.add_command(
            label="Save playlist",
            command=self.__save_playlist, state=DISABLED
        )
        self._playlist_menu.add_separator()
        self._playlist_menu.add_command(
            label="Gain scan",
            command=self._gain_scan
        )
        self._menubar.add_cascade(label="Playlist", menu=self._playlist_menu)

        self._gain_menu = Menu(self._menubar, tearoff=0)
        self._gain_menu.add_checkbutton(
            label="None",
            command=self.disable_gain,
            onvalue=GainModeEnum.NONE.value,
            variable=self.gain_mode.value
        )
        self._gain_menu.add_separator()
        self._gain_menu.add_checkbutton(
            label="Replay Gain Album",
            command=self.set_replay_gain_album,
            onvalue=GainModeEnum.REPLAY_GAIN_ALBUM.value,
            variable=self.gain_mode.value
        )
        self._gain_menu.add_checkbutton(
            label="Replay Gain Track",
            command=self.set_replay_gain_track,
            onvalue=GainModeEnum.REPLAY_GAIN_TRACK.value,
            variable=self.gain_mode.value
        )
        self._gain_menu.add_checkbutton(
            label="EBU R128 Gain Album",
            command=self.set_r128_gain_album,
            onvalue=GainModeEnum.R128_GAIN_ALBUM.value,
            variable=self.gain_mode.value
        )
        self._gain_menu.add_checkbutton(
            label="EBU R128 Gain Track",
            command=self.set_r128_gain_track,
            onvalue=GainModeEnum.R128_GAIN_TRACK.value,
            variable=self.gain_mode.value
        )
        self._menubar.add_cascade(label="Gain", menu=self._gain_menu)

        self._root.config(menu=self._menubar)

        timeline_kwargs = {"orient": HORIZONTAL, "showvalue": 0, "sliderlength": 10}
        if system() == "Windows":
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

        if system() == "Windows":
            self._playlist_box = gui.components.playlist.PlaylistWidget(self._root, width=48, height=0)
        else:
            self._playlist_box = gui.components.playlist.PlaylistWidget(self._root, width=40, height=0)
        if _playlist is not None and \
                (type(_playlist) is playlist.Playlist or type(_playlist) is playlist.DeserialisedPlaylist):
            self._playlist_box.playlist_initiation(
                _playlist.tags, self.select_item, self.open_album_dialogue, async_playlist_load
            )
        self._playlist_box.grid(row=3, column=0)

        self._playlist_controls = Frame(self._root)
        self._playlist_controls.grid(row=4, column=0)
        self._create_playlist_btn = ttk.Button(
            self._playlist_controls,
            text='New playlist',
            command=self._playlist_creator
        )
        self._create_playlist_btn.pack(side='left')
        self._index_dir_btn = ttk.Button(
            self._playlist_controls,
            text='Index dir',
            command=self._scan_dir
        )
        self._index_dir_btn.pack(side='left')
        self._add_tracks_btn = ttk.Button(
            self._playlist_controls,
            text='Add tracks',
            command=self._add_track_in_playlist
        )
        self._add_tracks_btn.pack(side='left')
        self._add_dir_btn = ttk.Button(
            self._playlist_controls,
            text='Add directory',
            command=self._add_directory_to_playlist
        )
        self._add_dir_btn.pack(side='left')

        self._status_bar = Frame(self._root)
        self._codec_label = Label(self._status_bar)
        self._codec_label.pack(side="left")
        self._bitrade_label = Label(self._status_bar)
        self._bitrade_label.pack(side="left")
        self._playstate_label = Label(self._status_bar)
        self._playstate_label.pack(side="left")
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
        self._root.bind("<space>", self._toggle_play_state)
        self._root.bind("<Left>", self.__seek_back)
        self._root.bind("<Right>", self.__seek_forward)
        self._keyboard_listener = pynput.keyboard.Listener(on_press=self.pynput_global_key_listener)
        self._keyboard_listener.start()

        self._root.mainloop()

    def _toggle_play_state(self, event=None):
        if self._playlist.is_playing():
            self._playlist.pause()
            self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
            self._playpause_btn.setPlay()
            self.__lock_prev_next_buttons()
            self._root.after_cancel(self._playing_timer)
        else:
            self._playlist.play()
            self._playpause_btn.setPause()
            self._playback_menu.entryconfig(1, state=NORMAL)
            self._current_track_number = self._playlist.get_current_position()['track']
            self._playing_update()

    def _stop(self, event=None):
        self._playlist.stop()
        self._playpause_btn.setPlay()
        self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
        self.__lock_prev_next_buttons()
        self._root.after_cancel(self._playing_timer)
        self._timeline.reset()
        self._playback_menu.entryconfig(1, state=DISABLED)

    def select_item(self, track):
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
        self._playlist.play_from_item(track)
        self._playback_menu.entryconfig(1, state=NORMAL)
        self._playing_update()
        self._playpause_btn.setPause()

    def _playing_update(self):
        if not self._playlist.is_end():
            self._playpause_btn.setPause()
            self._playing_timer = self._root.after(100, self._playing_update)
            Position = self._playlist.get_current_position()
            if Position['track'] > 0:
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
                int(self._playlist.tags[Position['track']].bitrate())) + 'kbps'
            self._playstate_label['text'] = "{} {}".format(
                self._playlist.playback_mode.name.lower(),
                gui.strings.PLAYBACK
            )
        else:
            self._playpause_btn.setReplay()

    def _timeline_ready(self):
        self._root.after_cancel(self._playing_timer)

    def _timeline_seek(self, position: float):
        self._playlist.seek(position)
        self._playing_timer = self._root.after(100, self._playing_update)
        self._playpause_btn.setPause()

    def _get_filelist(self):
        return filedialog.askopenfilenames(
            parent=self.loading_banner.root,
            title=gui.strings.SELECT_SOUND_FILES,
            filetypes=(
                (gui.strings.SOUND_FILES, support_sound_files_extensions),
                ("index files", "*.cue"),
                ("Winamp playlist", "*.m3u *.m3u8"),
                (gui.strings.ALL_FILES, "*.*")
            )
        )

    def _invalid_filename_exception_handler(self, e):
        messagebox.showerror(
            gui.strings.FILE_INDEXER,
            gui.strings.INVALID_FILENAME_NEWLINE + ascii(e.filename)
        )
        self._playlist = None
        self.clear()

    def _playlist_creator(self):
        self.display_loading_banner(True)
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
        self._timeline.reset()
        filelist = self._get_filelist()
        if len(filelist) > 0:
            try:
                self.loading_banner.progressbar['maximum'] = len(filelist)
                if self._playlist is not None:
                    self._playlist.clear()
                    del self._playlist
                self._playlist = playlist.Playlist(filelist, progressbar=self.loading_banner.progressbar)
                self._playlist.set_gui(self)
                self._playlist.playback_mode = self.playback_mode
                self._playlist.change_gain_mode(self.gain_mode)
                self.__unlock_playback_controls()
                self._playlist_box.playlist_initiation(
                    self._playlist.tags, self.select_item, self.open_album_dialogue
                )
            except tagIndexer.CUEparserError as e:
                messagebox.showerror(
                    gui.strings.CUE_INDEXER,
                    gui.strings.ERROR_AT_LINE_NEWLINE + e.line + e.message
                )
            except custom_exceptions.invalidFilename as e:
                self._invalid_filename_exception_handler(e)
            self._playpause_btn.setPlay()
            self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
            self.__lock_prev_next_buttons()
        elif self._playlist is not None and self._playlist.is_playing():
            self._playing_update()
        self.hide_loading_banner()

    def _add_track_in_playlist(self):
        self.display_loading_banner(True)
        self.freeze()
        filelist = self._get_filelist()
        if len(filelist):
            self.loading_banner.progressbar['maximum'] = len(filelist)
            try:
                self._playlist.add_files(filelist, progressbar=self.loading_banner.progressbar)
            except tagIndexer.CUEparserError as e:
                messagebox.showerror(
                    gui.strings.CUE_INDEXER,
                    gui.strings.ERROR_AT_LINE_NEWLINE + e.line + e.message
                )
            except custom_exceptions.invalidFilename as e:
                self._invalid_filename_exception_handler(e)
            else:
                self._playlist_box.append(self._playlist.tags, self.select_item, self.open_album_dialogue)
                if self._playlist.state():
                    self._playing_update()
        elif self._playlist is not None and self._playlist.is_playing():
            self._playing_update()
        self.hide_loading_banner()

    def _add_directory_to_playlist(self):
        self.display_loading_banner(True)
        self.freeze()
        directory = filedialog.askdirectory(
            parent=self.loading_banner.root,
            title="select music folder")
        if directory:
            try:
                self._playlist.add_files(
                    tagIndexer.folder_indexer(
                        directory,
                        progressbar=self.loading_banner.progressbar
                    )
                )
            except tagIndexer.CUEparserError as e:
                messagebox.showerror(
                    gui.strings.CUE_INDEXER,
                    gui.strings.ERROR_AT_LINE_NEWLINE + e.line + e.message
                )
            else:
                self._playlist_box.append(self._playlist.tags, self.select_item, self.open_album_dialogue)
                if self._playlist.state():
                    self._playing_update()
            self._playpause_btn.setPlay()
            self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
        elif self._playlist is not None and self._playlist.is_playing():
            self._playing_update()
        self.hide_loading_banner()

    def _scan_dir(self):
        self.display_loading_banner(True)
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
        directory = filedialog.askdirectory(
            parent=self.loading_banner.root,
            title="select music folder"
        )
        if len(directory):
            if self._playlist is not None:
                self._playlist.clear()
                del self._playlist
            try:
                self._playlist = playlist.Playlist(
                    tagIndexer.folder_indexer(
                        directory,
                        progressbar=self.loading_banner.progressbar
                    )
                )
                self._playlist.set_gui(self)
                self._playlist.playback_mode = self.playback_mode
                self._playlist.change_gain_mode(self.gain_mode)
            except tagIndexer.CUEparserError as e:
                messagebox.showerror(
                    gui.strings.CUE_INDEXER,
                    gui.strings.ERROR_AT_LINE_NEWLINE + e.line + e.message
                )
            else:
                self.__unlock_playback_controls()
                self._playlist_box.playlist_initiation(
                    self._playlist.tags, self.select_item, self.open_album_dialogue
                )
                self._playpause_btn.setPlay()
                self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
                self.__lock_prev_next_buttons()
        elif self._playlist is not None and self._playlist.is_playing():
            self._playing_update()
        self.hide_loading_banner()

    def __prev_track_change(self):
        Position = self._playlist.get_current_position()
        if not self._playlist.is_start():
            if self._playing_timer is not None:
                self._root.after_cancel(self._playing_timer)
            prev_track = Position['track'] - 1
            self._playlist.play_from_item(prev_track)
            if prev_track == 0:
                self._prev_btn.disable()
        self._playing_update()

    def __next_track_change(self):
        Position = self._playlist.get_current_position()
        if not self._playlist.is_end():
            if self._playing_timer is not None:
                self._root.after_cancel(self._playing_timer)
            next_track = Position['track'] + 1
            self._playlist.play_from_item(next_track)
            if next_track < (self._playlist.get_playlist_len() - 1):
                self._next_btn.enable()
            else:
                self._next_btn.disable()
        self._playing_update()

    def __lock_playback_controls(self):
        self._playpause_btn.disable()
        self._add_tracks_btn['state'] = 'disabled'
        self._add_dir_btn['state'] = 'disabled'
        self._prev_btn.disable()
        self._next_btn.disable()
        self._playback_menu.entryconfig(1, state=DISABLED)

    def __unlock_playback_controls(self):
        self._playpause_btn.enable()
        self._add_tracks_btn['state'] = 'normal'
        self._add_dir_btn['state'] = 'normal'
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

    def _set_playback_mode(self, mode):
        self._playlist.change_playback_mode(mode)
        self.playback_mode = mode

    def _set_gain_mode(self, mode):
        self._playlist.change_gain_mode(mode)
        self.gain_mode = mode

    def _set_mode(self, func, args):
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
        func(*args)
        if self._playlist.state():
            self._playing_update()

    def set_gapless_mode(self):
        self._set_mode(self._set_playback_mode, (PlaybackModeEnum.GAPLESS,))

    def set_crossfade_mode(self):
        self._set_mode(self._set_playback_mode, (PlaybackModeEnum.CROSSFADE,))

    def disable_gain(self):
        logger.info("disabling gain")
        self._set_mode(self._set_gain_mode, (GainModeEnum.NONE,))

    def set_replay_gain_album(self):
        logger.info("activation {} mode".format(GainModeEnum.REPLAY_GAIN_ALBUM.name.lower()))
        self._set_mode(self._set_gain_mode, (GainModeEnum.REPLAY_GAIN_ALBUM,))

    def set_replay_gain_track(self):
        logger.info("activation {} mode".format(GainModeEnum.REPLAY_GAIN_TRACK.name.lower()))
        self._set_mode(self._set_gain_mode, (GainModeEnum.REPLAY_GAIN_TRACK,))

    def set_r128_gain_album(self):
        logger.info("activation {} mode".format(GainModeEnum.R128_GAIN_ALBUM.name.lower()))
        self._set_mode(self._set_gain_mode, (GainModeEnum.R128_GAIN_ALBUM,))

    def set_r128_gain_track(self):
        logger.info("activation {} mode".format(GainModeEnum.R128_GAIN_TRACK.name.lower()))
        self._set_mode(self._set_gain_mode, (GainModeEnum.R128_GAIN_TRACK,))

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
        import pathlib
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
        filename = filedialog.asksaveasfilename(
            title=gui.strings.SAVE_PLAYLIST,
            filetypes=(
                (gui.strings.PLAYLIST, "*.cspl"),
                ("json", "*.cutieStreamer.json"),
                ("m3u extended playlist format", "*.m3u8")
            ),
            defaultextension=".cspl"
        )
        if filename:
            filename = pathlib.Path(filename)
            if filename.suffix.lower() == ".cspl":
                playlist.serizlize_playlist_file(filename, self._playlist, self)
            elif filename.suffix.lower() == ".json":
                self._playlist.serialize(filename)
            elif filename.suffix.lower() == ".m3u8":
                self._playlist.save_m3u8(filename)
        if self._playlist is not None and self._playlist.is_playing():
            self._playing_update()

    def set_playlist(self, _playlist, cover_thumbnails):
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
            self._timeline.reset()
        if self._playlist is not None:
            self._playlist.clear()
            del self._playlist
        self._playlist = _playlist
        self._playlist.set_gui(self)
        self._playlist.playback_mode = self.playback_mode
        self._playlist.change_gain_mode(self.gain_mode)
        self.__unlock_playback_controls()
        self._playlist_box.playlist_initiation(
            self._playlist.tags,
            self.select_item,
            self.open_album_dialogue,
            cover_thumbnails=cover_thumbnails
        )
        self._playpause_btn.setPlay()
        self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
        self.__lock_prev_next_buttons()

    def __open_playlist(self):
        self.display_loading_banner(True)
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)
            self._timeline.reset()
        filename = filedialog.askopenfilename(
            parent=self.loading_banner.root,
            title=gui.strings.SELECT_PLAYLIST,
            filetypes=(
                (gui.strings.PLAYLIST_FORMATS, "*.cspl *.cutieStreamer.json"),
                (gui.strings.PLAYLIST_FILE, "*.cspl"),
                ("json", "*.cutieStreamer.json"),
                (gui.strings.ALL_FILES, "*.*")
            )
        )
        if len(filename) > 0:
            if filename[-19:] == '.cutieStreamer.json':
                if self._playlist is not None:
                    self._playlist.clear()
                    del self._playlist
                self._playlist = playlist.DeserialisedPlaylist(filename)
                self._playlist.set_gui(self)
                self._playlist.playback_mode = self.playback_mode
                self._playlist.change_gain_mode(self.gain_mode)
                self.__unlock_playback_controls()
                self._playlist_box.playlist_initiation(
                    self._playlist.tags, self.select_item, self.open_album_dialogue
                )
                self._playpause_btn.setPlay()
                self._playstate_label['text'] = gui.strings.PLAYBACK_STOPPED
                self.__lock_prev_next_buttons()
            elif filename[-5:] == '.cspl':
                playlist.deserizlize_playlist_file(filename, self)
        elif self._playlist is not None:
            self._playing_update()
        self.hide_loading_banner()

    def __show_properties_frame(self):
        if self._playlist.is_playing():
            Position = self._playlist.get_current_position()
            self._trackPropertiesFrame = gui.dialogues.TrackProperties(
                self._root,
                self._playlist.tags[Position['track']],
                self
            )
        else:
            messagebox.showerror(
                gui.strings.DISPLAY_PROPERTIES,
                'Can\'t display track properties: nothing is playing'
            )

    def clear(self):
        self._playlist_box.clear()
        if self._playlist is not None:
            self._playlist.clear()
        self._playlist = None
        self._playpause_btn.disable()
        self._add_tracks_btn['state'] = 'disabled'
        self._add_dir_btn['state'] = 'disabled'
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

    def playlist__get_cover_thumbnails(self):
        return self._playlist_box.getCoverThumbnails()

    def freeze(self):
        if self._playing_timer is not None:
            self._root.after_cancel(self._playing_timer)

    def unfreeze(self):
        if self._playlist is not None and self._playlist.is_playing():
            self._playing_update()

    def open_album_dialogue(self, album, artist, tracks):
        self.freeze()
        gui.dialogues.AlbumDialogue(self._root, self, album, artist, tracks)

    def set_album_tags(self, tracks, new_album_artist, new_album, disc=None):
        self._playlist.setAlbumArtistTags(tracks, new_album_artist, new_album, disc)
        self.playlist_update()

    def playlist_update(self):
        self._playlist_box.playlist_initiation(
            self._playlist.tags, self.select_item, self.open_album_dialogue, True
        )

    def convert_album(self, tracks):
        self.freeze()
        converter.outdir = filedialog.askdirectory(
            parent=self._root,
            title=gui.strings.SELECT_OUTPUT_FOLDER
        )
        self.unfreeze()
        if not converter.outdir:
            return None
        convert_thread = threading.Thread(
            target=converter.convertPlaylist,
            args=(tracks, gui.dialogues.ConvertProgress(self._root))
        )
        convert_thread.start()

    def __seek_back(self, event):
        if self._playlist.is_playing():
            self._root.after_cancel(self._playing_timer)
            time = self._playlist.get_current_position()['time']
            self._playlist.seek(time - 10)
            self._playing_timer = self._root.after(100, self._playing_update)
            self._playpause_btn.setPause()

    def __seek_forward(self, event):
        if self._playlist.is_playing():
            self._root.after_cancel(self._playing_timer)
            time = self._playlist.get_current_position()['time']
            self._playlist.seek(time + 10)
            self._playing_timer = self._root.after(100, self._playing_update)
            self._playpause_btn.setPause()

    def pynput_global_key_listener(self, key):
        PLAY_PAUSE_MEDIA_KEY_CODES = (269025044, 269025073)
        PREV_TRACK_MEDIA_KEY_CODE = 269025046
        NEXT_TRACK_MEDIA_KEY_CODE = 269025047
        STOP_MEDIA_KEY_CODE = 269025045
        if self._playlist is not None:
            position = self._playlist.get_current_position()
            if key == pynput.keyboard.KeyCode(vk=PLAY_PAUSE_MEDIA_KEY_CODES[0]) or \
                    key == pynput.keyboard.KeyCode(vk=PLAY_PAUSE_MEDIA_KEY_CODES[1]):
                self._toggle_play_state()
            elif key == pynput.keyboard.KeyCode(vk=PREV_TRACK_MEDIA_KEY_CODE):
                if position['time'] > 15:
                    self._playlist.seek(0)
                elif (position['track'] - 1) >= 0:
                    self.__prev_track_change()
            elif key == pynput.keyboard.KeyCode(vk=NEXT_TRACK_MEDIA_KEY_CODE) and \
                    (position['track'] + 1) < self._playlist.get_playlist_len():
                self.__next_track_change()
            elif key == pynput.keyboard.KeyCode(vk=STOP_MEDIA_KEY_CODE):
                self._stop()

    def _gain_scan(self):
        self._stop()
        self.freeze()
        self.loading_banner = gui.dialogues.LoadingBanner(
            self._root,
            self._loading_banner_img,
            False
        )
        self.loading_banner.root.update()
        self._playlist.r128_playlist_scan(self.loading_banner)
        self.loading_banner.close()
        self.unfreeze()
