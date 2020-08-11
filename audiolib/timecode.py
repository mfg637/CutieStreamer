#!/usr/bin/python
# -*- coding: utf-8 -*-
#writed by: mfg637
import string
def parse(timecode):
	split_timecode=timecode.split(':')
	time=0
	if timecode.count('.'):
		for i in range(len(split_timecode)):
			time+=float(split_timecode[i])*(60**(len(split_timecode)-i-1))
	else:
		for i in range(len(split_timecode)):
			time+=int(split_timecode[i])*(60**(len(split_timecode)-i-1))
	return time
def encode(number):
	hours=0
	minutes=0
	seconds=0
	if number>=3600:
		hours=int(number)//3600
		number-=3600*hours
	if number>=60:
		minutes=int(number)//60
		number-=60*minutes
	seconds=number
	if type(seconds) is int:
		seconds=str(seconds).zfill(2)
	else:
		if seconds<10:
			seconds='0'+str(seconds)
		else:
			seconds=str(seconds)
	if hours:
		return str(hours)+':'+str(minutes).zfill(2)+':'+str(seconds).zfill(2)
	elif minutes:
		return str(minutes)+':'+str(seconds).zfill(2)
	else:
		return '0:'+str(seconds)
def CUEparse(CUEtimecode):
	minutes=0
	seconds=0
	frames=0
	split_timecode=CUEtimecode.split(':')
	minutes=int(split_timecode[0])
	seconds=int(split_timecode[1])
	frames=int(split_timecode[2])
	if frames==0:
		return minutes*60+seconds
	else:
		return minutes*60+seconds+frames//75.0
def CUEcode(sec):
	minutes=int(sec//60)
	seconds=int(sec)-minutes*60
	frames=int(round((sec-minutes*60-seconds)*75))
	timecode=''
	if minutes<10:
		timecode+='0'+str(minutes)+':'
	else:
		timecode+=str(minutes)+':'
	if seconds<10:
		timecode+='0'+str(seconds)+':'
	else:
		timecode+=str(seconds)+':'
	if frames<10:
		timecode+='0'+str(frames)
	else:
		timecode+=str(frames)
	return timecode	