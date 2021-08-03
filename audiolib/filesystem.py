#!/usr/bin/python3
# -*- coding: utf-8 -*-
#included module writed by mfg637

import os, platform, pathlib

def files(path):
	listfile = []
	for inode in os.listdir(path):
		if os.path.isfile(os.path.join(path, inode)):
			listfile.append(os.path.join(path, inode))
	return listfile


def files_p(root:pathlib.Path)->list:
	listfile = []
	for file in root.iterdir():
		if file.is_file():
			listfile.append(root.joinpath(file))
	return listfile


def directories(path):
	listdir = []
	for entry in path.iterdir():
		if entry.is_dir():
			listdir.append(entry)
	return listdir

def directories_tree(path):
	locallistdir = []
	listdir = []
	for entry in path.iterdir():
		if entry.is_dir():
			locallistdir.append(entry)
			listdir.append(entry)
	for directory in locallistdir:
		listdir+=directories_tree(directory)
	return listdir