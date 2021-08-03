import tkinter
import threading
from PIL import ImageTk
import gui.dialogues.CoverViewer


class TrackInfo(tkinter.Frame):
	_nocover_image = None
	def __init__(self, master, *args, **kwargs):
		tkinter.Frame.__init__(self, master, *args, **kwargs)
		self._parent_node = master
		self._cover_label = tkinter.Label(self, image=self._nocover_image)
		self._cover_label.grid(row=0, column=0, rowspan=3)
		self._cover_label.bind('<Button-1>', self.__open_cover_viewer)
		self._title_caption = tkinter.Label(self, text='Title:')
		self._title_caption.grid(row=0, column=1, sticky='e')
		self._title_label = tkinter.Label(self)
		self._title_label.grid(row=0, column=2, sticky='w')
		self._artist_captiom = tkinter.Label(self, text='Artist:')
		self._artist_captiom.grid(row=1, column=1, sticky='e')
		self._artist_label = tkinter.Label(self)
		self._artist_label.grid(row=1, column=2, sticky='w')
		self._album_caption = tkinter.Label(self, text='Album:')
		self._album_caption.grid(row=2, column=1, sticky='e')
		self._album_label = tkinter.Label(self)
		self._album_label.grid(row=2, column=2, sticky='w')
		self._track = None
		self._cover_img_raw = ''
		self._cover_update_thread = threading.Thread(target=self.__cover_update, args=('',))

	def update_track(self, track):
		tag = track.get_tags_list()
		self._track = track
		self._title_label['text'] = tag.title()[:36]
		self._artist_label['text'] = tag.artist()[:36]
		self._album_label['text'] = tag.album()[:36]
		if not self._cover_update_thread.is_alive():
			self._cover_update_thread = threading.Thread(target=self.__cover_update, args=(track,))
			self._cover_update_thread.start()

	def __cover_update(self, track):
		if track.cover() != self._cover_img_raw:
			self._cover_img_raw = track.cover()
			if track.cover() == '':
				self._cover_label['image']=self._nocover_image
			else:
				self._cover_img = ImageTk.PhotoImage(track.get_front_cover_image((64, 64), force=True))
				self._cover_label['image'] = self._cover_img

	def reset(self):
		self._title_label['text'] = ''
		self._artist_label['text'] = ''
		self._album_label['text'] = ''
		self._cover_label['image'] = self._nocover_image

	def __open_cover_viewer(self, event):
		self.__cover_viewer_obj = gui.dialogues.CoverViewer(self._parent_node, self._track)