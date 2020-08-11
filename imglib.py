#!/usr/bin/python3
# -*- coding: utf-8 -*-

from PIL import Image
import os


def get_max_resolution_image(imglist):
	sizes_list = []
	position = 0
	if len(imglist) > 0:
		for image in imglist:
			with Image.open(image) as img:
				sizes_list.append(img.size[0]*img.size[1])
		for i in range(len(sizes_list)):
			if sizes_list[i] > sizes_list[position]:
				position = i
		return imglist[position]
	else:
		return False


def rcalc(side, ratio, type):
	calculator={
		'width': int(round(side*ratio)),
		'height': int(round(side/ratio))
	}
	return calculator[type]


def resample(source, output, min=0, max='infinity', width='ratio', height='ratio', quality=90, hq=True):
	img = Image.open(source)
	if img.size[0]/img.size[1]>1.75:
		img=img.crop((img.size[0]-img.size[1], 0, img.size[0], img.size[1]))
	sourceWidth = img.size[0]
	sourceHeigth = img.size[1]
	width, height = resize(sourceWidth, sourceHeigth, min, max, width, height)
	if hq:
		resized=img.resize((width, height), Image.LANCZOS)
	else:
		resized=img.resize((width, height), Image.BOX)
	resized.save(output, quality=quality)
	img.close()
	return True

def resize(sourceWidth, sourceHeigth, min=0, max='infinity', width='ratio', height='ratio'):
	aspectRatio=float(sourceWidth)/float(sourceHeigth)
	if (width == 'ratio') & (height == 'ratio'):
		if (min>0) & (max!='infinity'):
			if aspectRatio>1:
				if rcalc(max, aspectRatio, 'height') <= min:
					height=rcalc(max, aspectRatio, 'height')
					width=max
				else:
					width=rcalc(min, aspectRatio, 'width')
					height=min
			elif aspectRatio<1:
				if rcalc(max, aspectRatio, 'width') <= min:
					width=rcalc(max, aspectRatio, 'width')
					height=max
				else:
					height=rcalc(min, aspectRatio, 'height')
					width=min
			else:
				width=min
				height=min
		elif min>0:
			if aspectRatio>1:
				height=min
				width=rcalc(min, aspectRatio, 'width')
			elif aspectRatio<1:
				width=min
				height=rcalc(min, aspectRatio, 'height')
			else:
				width=min
				height=min
		elif max!='infinity':
			if aspectRatio>1:
				width=max
				height=rcalc(max, aspectRatio, 'height')
			elif aspectRatio<1:
				height=max
				width=rcalc(max, aspectRatio, 'width')
			else:
				width=max
				height=max
		else:
			return False
	else:
		if (width!='ratio') & (height!='ratio'):
			if rcalc(width, aspectRatio, 'height')<=height:
				height = rcalc(width, aspectRatio, 'height')
			else:
				width = rcalc(height, aspectRatio, 'width')
		elif width!='ratio':
			height=rcalc(width, aspectRatio, 'height')
		elif height!='ratio':
			width=rcalc(height, aspectRatio, 'width')
	if (sourceWidth<width) & (sourceHeigth<height):
		width=sourceWidth
		height=sourceHeigth
	return (width, height)