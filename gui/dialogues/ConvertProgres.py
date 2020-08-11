from tkinter import Toplevel, Label, ttk


class ConvertProgress():
	def __init__(self, root):
		self._root = Toplevel(root)
		self._textIndication = Label(self._root, text="convert track i of n")
		self._textIndication.pack(side="top")
		# self._currentTrackInfo = Label(self._root)
		# self._currentTrackInfo.pack(side="top")
		self._progressbar = ttk.Progressbar(self._root, length=150)
		self._progressbar.pack(side="top")
		self._current_track = 1
		self._ntracks = 0

	def set_ntracks(self, n):
		self._ntracks = n
		self._textIndication['text'] = "convert track 1 of {}".format(n)
		self._progressbar['maximum'] = n

	def increment(self):
		self._current_track += 1
		self._textIndication['text'] = "convert track {} of {}".format(
			self._current_track,
			self._ntracks
		)
		self._progressbar.step()

	def update(self):
		self._textIndication.update()
		self._progressbar.update()

	def close(self):
		self._root.destroy()