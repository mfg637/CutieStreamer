from tkinter import Toplevel, Label

from PIL import ImageTk


class CoverViewer:
	def __init__(self, root, track):
		self._root = Toplevel(root)
		self._cover_label = Label(self._root)
		self._cover_label.pack()
		if track.cover() != '':
			self._cover_img = ImageTk.PhotoImage(track.get_front_cover_image((720, 720)))
			self._cover_label['image'] = self._cover_img