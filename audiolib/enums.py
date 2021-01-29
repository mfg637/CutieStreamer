import enum


class GainModeEnum(enum.Enum):
	NONE = 0
	REPLAY_GAIN_ALBUM = 1
	REPLAY_GAIN_TRACK = 2
	R128_GAIN_ALBUM = 3
	R128_GAIN_TRACK = 4