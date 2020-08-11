import tkinter
from audiolib import timecode

class TimeLine(tkinter.Scale):
	def __init__(
			self,
			master,
			current_time_label: tkinter.Label,
			total_time_label: tkinter.Label,
			ready_handler,
			seek_handler,
			*args, **kwargs):
		tkinter.Scale.__init__(self, master, *args, **kwargs)
		self.current_time_label = current_time_label
		self.total_time_label = total_time_label
		self._ready_handler = ready_handler
		self._seek_handler = seek_handler
		self.bind("<ButtonPress-1>", self._ready_event)
		self.bind("<ButtonRelease-1>", self._seek_event)
		self['to'] = 1
		self.set(0)
		self.current_time_label['text'] = "0:00"
		self.total_time_label['text'] = " 0:00"

	def _ready_event(self, event):
		x=event.x-10
		width=event.widget.winfo_width()-20
		self._ready_handler()
		self.set(self['to'] * (x / width))

	def _seek_event(self, event):
		self._seek_handler(event.widget.get()/10)

	def update_track_position(self, Position: dict, tag):
		self['to'] = tag.duration() * 10
		self.set(Position['time'] * 10)
		self.current_time_label['text'] = timecode.encode(int(Position['time']))
		self.total_time_label['text'] = ' '+timecode.encode(int(tag.duration()))

	def reset(self):
		self['to'] = 1
		self.set(0)
		self.current_time_label['text'] = "0:00"
		self.total_time_label['text'] = " 0:00"