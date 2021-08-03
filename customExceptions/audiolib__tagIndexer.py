class CUEparserError(Exception):
	def __init__(self, line, message):
		self.line = line
		self.message = message


class CUEDecodeError(Exception):
	def __init__(self, file):
		self.file = file