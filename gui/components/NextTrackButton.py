from .ImageButtonMenuItem import ImageButtonMenuItem


class NextTrackButton(ImageButtonMenuItem):
	_nextbtn_img = None
	_nextbtn_img_active = None

	def __init__(self, master, timeline_ready_handler, next_track_handler, *args, **kwargs):
		ImageButtonMenuItem.__init__(self, master, *args, **kwargs)
		self._timeline_ready_handler = timeline_ready_handler
		self._next_track_handler = next_track_handler
		self['image'] = self._nextbtn_img

	def _menu_label(self) -> str:
		return "Next track"

	def _active(self, event):
		if self._enabled:
			self['image'] = self._nextbtn_img_active
			self._timeline_ready_handler()

	def _click_handler(self, event=None):
		self._next_track_handler()
		self['image'] = self._nextbtn_img
