from tkinter import Toplevel, ttk, Entry, messagebox, END


class AlbumDialogue:
	def __init__(self, root, parent, album, album_artist, tracks):
		self._my_parrent=parent
		self._root = Toplevel(root)
		self._tracks = tracks
		ttk.Label(self._root, text='Album Artist: ').grid(row=0, column=0, sticky='e')
		artists = set()
		for tag in tracks:
			if tag.getArtist() is not None:
				artists.add(tag.getArtist())
		artists.add("Various Artists")
		artists=list(artists)
		artists.insert(0, album_artist)
		self._album_artist_field = ttk.Combobox(self._root, values=artists)
		self._album_artist_field.grid(row=0, column=1, columnspan=2)
		self._album_artist_field.set(album_artist)
		ttk.Label(self._root, text='Album: ').grid(row=1, column=0, sticky='e')
		self._album_field = Entry(self._root, text=album, width=22)
		self._album_field.grid(row=1, column=1, columnspan=2)
		self._album_field.delete(0, END)
		self._album_field.insert(0, album)
		ttk.Label(self._root, text='Disc: ').grid(row=2, column=0, sticky='e')
		self._disc_field = Entry(self._root, width=22)
		self._disc_field.grid(row=2, column=1, columnspan=2)
		ttk.Button(self._root, text="Convert", command=self.__convertAlbum).grid(row=3, column=0)
		ttk.Button(self._root, text="OK", command=self.__setAlbumTags).grid(row=3, column=1)
		ttk.Button(self._root, text="Cancel", command=self.close).grid(row=3, column=2)
		ttk.Button(self._root, text="Decode", command=self.__decode).grid(row=4, column=0)
	def __setAlbumTags(self):
		disc = self._disc_field.get()
		if len(disc)>0:
			try:
				disc = int(disc)
			except ValueError:
				messagebox.showerror('Tag edit', 'invalid disc number')
				return None
		else:
			disc=None
		self._my_parrent.set_album_tags(
			self._tracks,
			self._album_artist_field.get(),
			self._album_field.get(),
			disc
		)
		self.close()
	def __convertAlbum(self):
		self.close()
		self._my_parrent.convert_album(self._tracks)
	def close(self):
		self._my_parrent.unfreeze()
		self._root.destroy()
	def __decode(self, event=None):
		for track in self._tracks:
			track.decode()
		self._my_parrent.playlist_update()
		self.close()