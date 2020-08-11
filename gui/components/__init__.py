from .ScrolledFrame import VerticalScrolledFrame
from . import playlist
from .timeline import TimeLine
from .TrackInfo import TrackInfo
from .PlayPauseButton import PlayPauseButton
from .PreviousTrackButton import PreviousTrackButton
from .NextTrackButton import NextTrackButton


def init(curdir):
	import tkinter
	import os
	from PIL import Image, ImageTk
	TrackInfo._nocover_image = tkinter.PhotoImage(
		file=os.path.join(curdir, 'images', "no_cover.gif")
	)
	_playbtn_PIL = Image.open(os.path.join(curdir, 'images', "play.png"))
	PlayPauseButton._playbtn_img = ImageTk.PhotoImage(_playbtn_PIL)
	PlayPauseButton._playbtn_img_active = ImageTk.PhotoImage(
		_playbtn_PIL.transpose(Image.FLIP_TOP_BOTTOM)
	)
	_playbtn_PIL.close()
	_pausebtn_PIL = Image.open(os.path.join(curdir, 'images', "pause.png"))
	PlayPauseButton._pausebtn_img = ImageTk.PhotoImage(_pausebtn_PIL)
	PlayPauseButton._pausebtn_img_active = ImageTk.PhotoImage(
		_pausebtn_PIL.transpose(Image.FLIP_TOP_BOTTOM)
	)
	_pausebtn_PIL.close()
	_replaybtn_PIL = Image.open(os.path.join(curdir, 'images', "replay.png"))
	PlayPauseButton._replaybtn_img = ImageTk.PhotoImage(_replaybtn_PIL)
	_replaybtn_PIL.close()
	_replaybtn_active_PIL = Image.open(os.path.join(curdir, 'images', "replay_active.png"))
	PlayPauseButton._replaybtn_img_active = ImageTk.PhotoImage(
		_replaybtn_active_PIL
	)
	_replaybtn_active_PIL.close()
	_prevbtn_PIL = Image.open(os.path.join(curdir, 'images', "prev.png"))
	PreviousTrackButton._prevbtn_img = ImageTk.PhotoImage(_prevbtn_PIL)
	PreviousTrackButton._prevbtn_img_active = ImageTk.PhotoImage(
		_prevbtn_PIL.transpose(Image.FLIP_TOP_BOTTOM)
	)
	NextTrackButton._nextbtn_img = ImageTk.PhotoImage(
		_prevbtn_PIL.transpose(Image.FLIP_LEFT_RIGHT)
	)
	NextTrackButton._nextbtn_img_active = ImageTk.PhotoImage(
		_prevbtn_PIL.rotate(180)
	)
	_prevbtn_PIL.close()