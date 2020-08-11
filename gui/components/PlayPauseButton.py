from .ImageButtonMenuItem import ImageButtonMenuItem


class PlayPauseButton(ImageButtonMenuItem):
	_playbtn_img = None
	_playbtn_img_active = None
	_pausebtn_img = None
	_pausebtn_img_active = None
	_replaybtn_img = None
	_replaybtn_img_active = None

	def __init__(self, master, timeline_ready_handler, toggle_play_pause_handler, *args, **kwargs):
		ImageButtonMenuItem.__init__(self, master, *args, **kwargs)
		self['image'] = self._playbtn_img
		self._timeline_ready_handler = timeline_ready_handler
		self._toggle_play_pause_handler = toggle_play_pause_handler
		self._playbtn = True
		self._replaybtn = False

	def _menu_label(self) -> str:
		return "Play/Pause"

	def _click_handler(self, event=None):
		self._toggle_play_pause_handler()

	def setPlay(self):
		self._playbtn = True
		self._replaybtn = False
		self['image'] = self._playbtn_img

	def setPause(self):
		self._playbtn = False
		self._replaybtn = False
		self['image'] = self._pausebtn_img

	def setReplay(self):
		self._replaybtn = True
		self['image'] = self._replaybtn_img

	def _active(self, event):
		if self._enabled:
			if self._replaybtn:
				self['image'] = self._replaybtn_img_active
			elif self._playbtn:
				self['image'] = self._playbtn_img_active
			else:
				self['image']=self._pausebtn_img_active
				self._timeline_ready_handler()
