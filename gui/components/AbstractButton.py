from abc import ABC, abstractmethod


class AbstractButton(ABC):
	def __init__(self):
		self._enabled = True

	@abstractmethod
	def _click_handler(self, event=None):
		pass

	def _click_event(self, event=None):
		if self._enabled:
			self._click_handler(event)