from tkinter import  Toplevel, Label, ttk, Entry
from audiolib import timecode


class TrackProperties:
	def __init__(self, root, track, main_gui_obj):
		tags = track.get_tags_list()
		self._root = Toplevel(root)
		main_gui_obj.freeze()
		self._main_gui_obj=main_gui_obj
		properies_list={
			'filename': track.filename(),
			'duration': timecode.encode(int(track.duration())),
			'codec': track.codec(),
			'bitrate': str(track.bitrate())+' kbps',
			'sample rate': track.sample_rate(),
			'encoder': tags.encoder()
		}
		i=1
		Label(self._root, text='Propety: ').grid(row=0, column=0, sticky='e')
		Label(self._root, text='Value').grid(row=0, column=1, sticky='w')
		for property in properies_list.keys():
			Label(self._root, text=property+': ').grid(row=i, column=0, sticky='e')
			e=Entry(self._root, width=100)
			e.insert(0, properies_list[property])
			e.grid(row=i, column=1, sticky='w')
			i+=1
		taglist=tags.get_tags()
		for tag in taglist.keys():
			Label(self._root, text=tag+': ').grid(row=i, column=0, sticky='e')
			e=ttk.Entry(self._root, width=100)
			e.insert(0, taglist[tag])
			e.grid(row=i, column=1, sticky='w')
			i+=1
		close_btn=ttk.Button(self._root, text="Ok", command=self.close)
		close_btn.grid(row=i, column=1, sticky='e')
		self._root.protocol("WM_DELETE_WINDOW", self.close)
	def close(self):
		self._main_gui_obj.unfreeze()
		self._root.destroy()