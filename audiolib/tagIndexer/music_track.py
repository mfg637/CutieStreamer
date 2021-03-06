import platform
import re
import os
import io
import PIL.Image
from ..enums import GainModeEnum
from .tags_list import TagsList
from .gain_constants import REPLAY_GAIN_LEVEL, EBU_R128_GAIN_LEVEL
import ffmpeg_prober
import imglib


def decodeTags(text:str, from_charset, to_charset):
	bintext = text.encode(from_charset)
	return bintext.decode(to_charset)


class MusicTrack:

	def __init__(self, *, codec=None, bitrate=None, channels=None,
					filename=None, start=None,
					duration=None, cover=None, sample_rate=None, cdesk=None,
					chandesk=None, format_name=None, is_custom_duration=False,
					raw_cover:bytes=None, cover_track_num=None, #**tags): DEPRECATED
				 	tags:TagsList, track_gain=None, album_gain=None
				 ):
		self._is_custom_duration = is_custom_duration
		self._sample_rate = sample_rate
		self._start = start
		self._duration = duration
		self._codec = codec
		self._cdesk = cdesk
		self._bitrate = bitrate
		self._channels = channels
		self._chandesk = chandesk
		self._filename = filename
		self._f = format_name
		self._embeded_cover = True if raw_cover is not None else False
		self._raw_cover = raw_cover
		self._chapters = []
		self._cover_track_num = cover_track_num
		self._taglist = tags
		self._cover = cover
		self._r128_track_gain = track_gain
		self._r128_album_gain = album_gain

	def is_custom_duration(self):
		return self._is_custom_duration

	def get_tags_list(self):
		return self._taglist

	def codec(self):
		return self._codec

	def bitrate(self):
		if self._bitrate:
			return self._bitrate
		else:
			return 0

	def channels(self):
		return self._channels

	def start(self):
		return self._start

	def duration(self):
		return self._duration

	def cover(self):
		if self._cover:
			return self._cover
		else:
			return ''

	def hasEmbededCover(self):
		return self._embeded_cover

	def sample_rate(self):
		return self._sample_rate

	def filename(self):
		return self._filename

	def container(self):
		return self._f

	def serialize(self, playlist_dir):
		cover_replace = False
		if platform.system() == 'Windows':
			filename = os.path.relpath(self._filename, start=playlist_dir)
			if not os.path.isabs(filename):
				cover_replace = True
				filename = re.sub('\\\\', '/', filename)
		else:
			filename = os.path.relpath(self._filename, start=playlist_dir)
		if type(self._cover) is int:
			cover = self._cover
		elif type(self._cover) is str:
			cover = os.path.relpath(self._cover, start=playlist_dir)
			if cover_replace:
				cover = re.sub('\\\\', '/', cover)
		else:
			cover = ''
		tags = self.get_tags_list()
		return {'tags': tags.get_tags(), 'start': self._start, 'duration': self._duration,
				'codec': self._codec, 'cdesk': self._cdesk, 'bitrate': self._bitrate,
				'channels': self._channels, 'chandesk': self._chandesk,
				'filename': filename,
				'cover': cover, "custom_duration": self._is_custom_duration,
				'embeded cover': self._embeded_cover, 'sample rate': self._sample_rate,
				'container': self._f, 'cover track index': self._cover_track_num,
				'r128_track_gain': self._r128_track_gain,
				'r128_album_gain': self._r128_album_gain}

	def getRawCover(self):
		return self._raw_cover

	def getCoverIndex(self):
		return self._cover_track_num

	def decode(self):
		for key in self._tags.keys():
			if type(self._tags[key]) is str:
				self._tags[key] = decodeTags(self._tags[key], 'cp1252', 'cp1251')

	def get_front_cover_image(self, size:tuple, force=False):
		if self._embeded_cover and self._raw_cover is not None:
			img = PIL.Image.open(io.BytesIO(self._raw_cover))
			if force:
				return img.resize(size, PIL.Image.LANCZOS)
			else:
				return img.resize(
						imglib.resize(
							img.size[0],
							img.size[1],
							width=size[0],
							height=size[1]
					), PIL.Image.LANCZOS
				)
		elif self._embeded_cover:
			imgBuffer = io.BytesIO(
				ffmpeg_prober.getPPM_Image(
					self._filename,
					size='{}x{}'.format(*size),
					force=force,
					index=self._cover_track_num
				)
			)
			return PIL.Image.open(imgBuffer)
		elif self._cover:
			img = PIL.Image.open(self._cover)
			if img.size[0] / img.size[1] > 1.75:
				img = img.crop((img.size[0] - img.size[1], 0, img.size[0], img.size[1]))
			if force:
				return img.resize(size, PIL.Image.LANCZOS)
			else:
				return img.resize(
						imglib.resize(
						img.size[0],
						img.size[1],
						width=size[0],
						height=size[1]
					), PIL.Image.LANCZOS)
		else:
			return None

	def set_r128_track_gain(self, r128_track):
		self._r128_track_gain = r128_track

	def get_r128_track_level(self):
		return self._r128_track_gain

	def get_replay_gain_track_level(self):
		if self._r128_track_gain is not None:
			return self._r128_track_gain + 5

	def _gain(self, current_level, target_level):
		return target_level - current_level

	def r128_track_gain(self):
		target_volume_dbFS = EBU_R128_GAIN_LEVEL
		if self._r128_track_gain is not None:
			return self._gain(self._r128_track_gain, target_volume_dbFS)

	def replay_gain_track(self):
		target_volume_dbFS = REPLAY_GAIN_LEVEL
		if self._r128_track_gain is not None:
			return self._gain(self._r128_track_gain, target_volume_dbFS)

	def set_r128_album_gain(self, r128_album):
		self._r128_album_gain = r128_album

	def get_r128_album_gain(self):
		return self._r128_album_gain

	def get_replay_gain_album(self):
		if self._r128_album_gain is not None:
			return self._r128_album_gain + 5

	def r128_album_gain(self):
		target_volume_dbFS = EBU_R128_GAIN_LEVEL
		if self._r128_album_gain is not None:
			return self._gain(self._r128_album_gain, target_volume_dbFS)
		else:
			return self.r128_track_gain()

	def replay_gain_album(self):
		target_volume_dbFS = REPLAY_GAIN_LEVEL
		if self._r128_album_gain is not None:
			return self._gain(self._r128_album_gain, target_volume_dbFS)
		else:
			return self.replay_gain_track()

	def get_gain_levels(self):
		return {
			GainModeEnum.NONE: None,
			GainModeEnum.R128_GAIN_ALBUM: self.r128_album_gain(),
			GainModeEnum.R128_GAIN_TRACK: self.r128_track_gain(),
			GainModeEnum.REPLAY_GAIN_ALBUM: self.replay_gain_album(),
			GainModeEnum.REPLAY_GAIN_TRACK: self.replay_gain_track()
		}

	def print_metadata(self):
		print(self._filename)
		print(self._f+" "+self._codec+" "+str(self._bitrate)+"k "+self._chandesk)
		self._taglist.print_metadata()
