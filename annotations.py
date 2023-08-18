"""
# Refraction cursor annotations for completion support and ephemeral information displays.
"""
from fault.system import files
from . import types
from . import location

def delimit(ai):
	"""
	# Apply common framing to an annotations primary image.
	"""

	yield ('field-annotation-start', ' (')
	yield from ai.image()
	if ai.title:
		yield ('field-annotation-separator', ' ')
		yield ('field-annotation-title', ai.title)
	yield ('field-annotation-stop', ')')

def extend(ai, lfields):
	"""
	# Unconditionally insert the delimited annotation at the end of &lfields.
	"""

	ifields = iter(lfields)
	yield from ifields
	yield from delimit(ai)

def at(ai, lfields, offset, *, len=len):
	"""
	# Insert the delimited annotation into &lfields after &offset.
	"""

	current = 0
	ifields = iter(lfields)

	for f in ifields:
		yield f
		current += len(x[1])
		if current >= offset:
			# Finish ifields after loop.
			yield from delimit(ai)
			break
	else:
		yield from delimit(ai)

	yield from ifields

class Directory(object):
	"""
	# Directory query annotation.

	# Provides common features for completion support.
	"""

	def __init__(self, title):
		self.title = title

		self.context = None
		self.location = None
		self.index = 0
		self.status = None
		self.snapshot = []
		self.matches = []

	def close(self):
		del self.snapshot[:]
		del self.matches[:]
		self.location = None
		self.context = None
		self.index = None
		self.status = None

	@staticmethod
	def file_name_priority(string):
		"""
		# Sort key for ordering some operator charcters after.
		"""

		if string[:1] in {'.', '_', '-', '~'}:
			return (1, string)
		else:
			return (0, string)

	def chdir(self, context, location):
		"""
		# Update the &Directory.context and &Directory.location attributes.
		"""

		self.context = context
		self.location = location

	def select(self, query):
		self.matches = [
			y.identifier
			for y in self.snapshot
			if y.identifier.startswith(query) or not query
		]
		self.status = query
		self.index = 0

	def sample(self, limit=8):
		"""
		# Get a sample of the next characters that will match.
		"""

		ms = set()
		offset = len(self.status)
		for m in self.matches:
			if len(ms) > limit:
				break
			ms.add(m[offset:offset+1])

		prefixset = sorted(ms, key=self.file_name_priority)
		if len(prefixset) > 0:
			prefixsample = "".join(prefixset)
		else:
			prefixsample = ""

		return prefixsample

	def rotate(self):
		self.index += 1
		if self.index >= len(self.matches):
			self.index = 0

	def image(self):
		try:
			istr = self.matches[self.index]
		except:
			istr = ''

		if istr and istr != self.status:
			yield from self.structure_path(istr)
			yield ('field-annotation-separator', ' ')

		yield ('literal-words', f"{len(self.matches)}/{len(self.snapshot)}")
		ds = self.sample()
		if ds:
			yield ('field-annotation-separator', '[')
			yield ('literal-words', f"{self.sample()}")
			yield ('field-annotation-separator', ']')

	def insertion(self):
		if self.index < len(self.matches):
			return self.matches[self.index][len(self.status):]
		else:
			return ""

class Filesystem(Directory):
	"""
	# Filesystem Directory query annotation for file path completion support.
	"""

	def __init__(self, title, structure, elements, vertical, horizontal):
		super().__init__(title)
		self.structure = structure
		self.elements = elements
		self.vertical = vertical
		self.horizontal = horizontal

	def structure_path(self, match):
		return location.format_path(self.location, [match])

	def chdir(self, context, location):
		super().chdir(context, location)
		self.snapshot = list(self.location.fs_iterfiles())

	def update(self, line, structure):
		ln = self.vertical.get()
		if ln == 0:
			rpath = files.root
		else:
			rpath = (files.root@self.elements[0])

		# Identify field.
		current = self.horizontal.get()
		prefix = line.rfind('/', 0, current)
		if prefix == -1:
			# No slash before cursor.
			prefix = self.start = 0
		else:
			# Position after slash.
			self.start = prefix + 1

		self.stop = line.find('/', max(current, self.start))
		if self.stop == -1:
			self.stop = len(line)

		# Update location.
		pathstr = line[:prefix]
		if pathstr:
			if pathstr.startswith('/'):
				path = rpath@pathstr
			else:
				path = rpath@(pathstr.strip('/'))
		else:
			path = rpath

		# Check for leading path changes.
		if self.location != path:
			# Update &snapshot.
			self.chdir(rpath, path)

		# Get the current query string (prefix).
		status = line[self.start:self.stop]
		if self.status != status:
			# Update &matches.
			self.select(status)
