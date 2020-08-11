
# -*- coding: utf-8 -*-

import abc
import struct
from zlib import crc32

class IncorrectPlaylistFile(Exception):
    def __init__(self, file):
        self.file=file

class PlaylistWriter:
    def __init__(self, filename):
        self._outfile=open(filename, 'bw')
        self._outfile.write(b"CutieStreamerPlaylist\x01")
        self._isclosed = False

    def write_chunk(self, data:bytes):
        self._outfile.write(struct.pack("<I", len(data)))
        self._outfile.write(data)
        self._outfile.write(struct.pack("<I", crc32(data)))

    def close(self):
        self._outfile.write(b'\x00\x00\x00\x00')
        self._outfile.close()
        self._isclosed = True
    
    def __del__(self):
        if not self._isclosed:
            self.close()


class PlaylistReader:
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def __init__(self, file):
        self._file = file
        self._eof = False
    @abc.abstractmethod
    def EOF(self):
        pass
    @abc.abstractmethod
    def read_chunk(self):
        pass
    def close(self):
        self._file.close()


class PlaylistReader0(PlaylistReader):
    def __init__(self, file):
        self._file = file
        self._current_chunk_size = struct.unpack("<I", file.read(4))[0]
    def EOF(self):
        return self._current_chunk_size == 0
    def read_chunk(self):
        data = self._file.read(self._current_chunk_size)
        self._current_chunk_size = struct.unpack("<I", self._file.read(4))[0]
        return data


class PlaylistReader1(PlaylistReader0):
    def __init__(self, file):
        PlaylistReader0.__init__(self, file)
    def read_chunk(self):
        data = self._file.read(self._current_chunk_size)
        crc_hash, self._current_chunk_size = struct.unpack("<II", self._file.read(8))
        if crc_hash == crc32(data):
            return data
        else:
            return None


format_handlers = {
    b"\x00": PlaylistReader0,
    b"\x01": PlaylistReader1
}


def open_playlist(filename):
    file = open(filename, 'br')
    format_id=file.read(21)
    if format_id!=b"CutieStreamerPlaylist":
        raise IncorrectPlaylistFile(filename)
    format_version = file.read(1)
    try:
        return format_handlers[format_version](file)
    except KeyError:
        raise IncorrectPlaylistFile(filename)