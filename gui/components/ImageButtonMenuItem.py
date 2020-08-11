from abc import ABC, abstractmethod
from .AbstractButton import AbstractButton
import tkinter


class ImageButtonMenuItem(AbstractButton, tkinter.Label, ABC):
	def __init__(self, master, *args, **kwargs):
		AbstractButton.__init__(self)
		tkinter.Label.__init__(self, master, *args, **kwargs)
		self._main_menu_group = None
		self._menu_item = None
		self.bind('<ButtonPress-1>', self._active)
		self.bind('<ButtonRelease-1>', self._click_event)

	@abstractmethod
	def _menu_label(self) -> str:
		return ''

	@abstractmethod
	def _active(self, event):
		pass

	def bind_menu_item(self, main_menu_group, menu_item):
		self._main_menu_group = main_menu_group
		self._menu_item = menu_item
		self._main_menu_group.add_command(label=self._menu_label(),
			command=self._click_event, state=(tkinter.NORMAL if self._enabled else tkinter.DISABLED))

	def enable(self):
		self._enabled = True
		self['state'] = tkinter.NORMAL
		self._main_menu_group.entryconfig(self._menu_item, state=tkinter.NORMAL)
		#print("\"{}\" button enabled".format(self._menu_label()))

	def disable(self):
		self._enabled = False
		self['state'] = tkinter.DISABLED
		self._main_menu_group.entryconfig(self._menu_item, state=tkinter.DISABLED)
		#print("\"{}\" button disabled".format(self._menu_label()))