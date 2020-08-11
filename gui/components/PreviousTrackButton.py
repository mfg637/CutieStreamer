from .ImageButtonMenuItem import ImageButtonMenuItem


class PreviousTrackButton(ImageButtonMenuItem):
	_prevbtn_img = None
	_prevbtn_img_active = None

	def __init__(self, master, timeline_ready_handler, prev_track_handler, *args, **kwargs):
		ImageButtonMenuItem.__init__(self, master, *args, **kwargs)
		self._timeline_ready_handler = timeline_ready_handler
		self._prev_track_handler = prev_track_handler
		self['image'] = self._prevbtn_img

	def _menu_label(self) -> str:
		return "Previous track"

	def _active(self, event):
		if self._enabled:
			self['image'] = self._prevbtn_img_active
			self._timeline_ready_handler()

	def _click_handler(self, event=None):
		self._prev_track_handler()
		self['image'] = self._prevbtn_img
