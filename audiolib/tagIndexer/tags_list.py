import os
import logging
import re


num = re.compile(r"\d+")
logger = logging.getLogger(__name__)


class TagsList:
	_tag_param = ['artist', 'title', 'track', 'genre', 'album', 'album_artist', 'date', 'publisher', 'disc']
	_important_tags = ['title', 'track', 'album', 'album_artist']

	def __init__(self, _tags: dict, filename: str):
		self._tags = _tags
		self._filename = filename

	def title(self):
		if 'title' in self._tags:
			return self._tags['title']
		else:
			return os.path.splitext(os.path.basename(self._filename))[0]

	def getTitle(self):
		if 'title' in self._tags:
			return self._tags['title']
		else:
			return None

	def artist(self):
		if 'artist' in self._tags:
			return self._tags['artist']
		else:
			return "unknown artist"

	def getArtist(self):
		if 'artist' in self._tags:
			return self._tags['artist']
		else:
			return None

	def track(self):
		if 'track' in self._tags:
			track = self.__getItem(self._tags['track'])
			if len(track) < 2:
				return '0' + str(track)
			else:
				return str(track)
		else:
			return "00"

	def getTrack(self):
		if 'track' in self._tags:
			return str(self.__getItem(self._tags['track']))
		else:
			return None

	def genre(self):
		if 'genre' in self._tags:
			return self._tags['genre']
		else:
			return None

	def album(self):
		if 'album' in self._tags:
			return self._tags['album']
		else:
			return "untitled"

	def getAlbum(self):
		if 'album' in self._tags:
			return self._tags['album']
		else:
			return None

	def setAlbum(self, value):
		self._tags['album'] = value

	def album_artist(self):
		if 'album_artist' in self._tags:
			return self._tags['album_artist']
		else:
			return "unknown"

	def getAlbumArtist(self):
		if 'album_artist' in self._tags:
			return self._tags['album_artist']
		else:
			return None

	def setAlbumArtist(self, value):
		self._tags['album_artist'] = value

	def date(self):
		if 'date' in self._tags:
			return self._tags['date']
		else:
			return None

	def get_tags(self):
		return self._tags

	def disc(self):
		if 'disc' in self._tags:
			return self.__getItem(self._tags['disc'])
		else:
			return None

	def set_disc(self, value):
		self._tags['disc'] = value

	@staticmethod
	def __getItem(FF_num):
		if type(FF_num) is str:
			return FF_num.split('/')[0]
		else:
			return str(FF_num)

	def track_num(self):
		if 'track' in self._tags:
			regex_match = num.match(self._tags['track'])
			logger.debug("track num = %s", regex_match)
			if regex_match is not  None:
				return int(regex_match[0])

	def disc_num(self):
		if 'disc' in self._tags:
			regex_match = num.match(self._tags['disc'])
			logger.debug("disc num = %s", regex_match)
			if regex_match is not None:
				return int(regex_match[0])

	def ffmetamarkup(self):
		ffmetadata=';FFMETADATA1'
		for param in self._tag_param:
			if param in self._tags:
				ffmetadata += "\n{}={}".format(param, self._tags[param])
		return ffmetadata

	def encoder(self):
		if 'encoder' in self._tags:
			return self._tags['encoder']
		else:
			return ''
