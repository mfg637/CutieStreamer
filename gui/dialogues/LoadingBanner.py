from platform import system
from tkinter import  Toplevel, Label, ttk


class LoadingBanner:
	def __init__(self, root, banner_img, window_raise=False):
		self.root = Toplevel(root)
		if system()=='Windows':
			self.root.overrideredirect(True)
		if window_raise:
			self.root.tkraise(root)
		self._image_label1=Label(self.root, image=banner_img)
		self._image_label1.pack()
		self.progressbar = ttk.Progressbar(self.root)
		self.progressbar.place(x=8, y=90, width=120)
		self.root.geometry(("%dx%d+%d+%d" % (256, 128,
			root.winfo_x()+30, root.winfo_y()+120)))
	def close(self):
		self.root.destroy()
	def __del__(self):
		self.root.destroy()