"""
# Refraction cursor annotations for completion support and ephemeral information displays.
"""
import functools
from typing import Sequence

from fault.system import files
from . import types
from . import location
from . import format

def rotate(ai, quantity=1):
	"""
	# Standard selection change.
	"""

	ai.index += quantity
	n = len(ai.selections)

	if ai.index >= n:
		ai.index = 0
	elif ai.index < 0:
		ai.index = n

	return ai.index

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

def integer_value(string, *, default=10, xlate=str.maketrans({x:' ' for x in ':,./'})):
	"""
	# Identify &string as a integer value.

	# [ Returns ]
	# The sign and the recognized integer value or &None if the string's format
	# could not be identified.
	"""

	rstring = ""
	s = string.strip().lower()
	if s.startswith('-'):
		sign = -1
		offset = 1
	else:
		offset = 0
		sign = 1

	first = s[offset:offset+1]
	pair = s[offset:offset+2]

	if first in '0#':
		# Likely explicit qualification.

		if pair == '0x':
			# Hex.
			offset += 2
			b = 16
		elif first == '#':
			# Hex Color.
			offset += 1
			b = 16
		elif pair == '0d':
			offset += 2
			b = 10
		elif pair == '0b':
			offset += 2
			b = 2
		elif pair == '0o':
			offset += 2
			b = 8
		else:
			# Not qualified, use default.
			# For many cases, decimal is the reasonable choice,
			# but in color values, hex is more likely.
			b = default

		try:
			iv = int(s[offset:], b)
		except Exception:
			iv = None
	elif s.strip(':').startswith('rgb:') and '/' in s:
		# xorg rgb:xx/xx/xx
		ss = s.strip(':')[4:].translate(xlate).split()
		try:
			decs = list(int(x, 16) for x in ss)
		except Exception:
			iv = None
		else:
			iv = 0
			for v in decs[:3]:
				iv = iv << 8
				iv += min(255, v)
	elif s.startswith('rgb'):
		# CSS rgb/rgba() strings.
		ss = s.strip(' ()rgba').translate(xlate).split()
		try:
			decs = list(int(x, 10) for x in ss)
		except Exception:
			iv = None
		else:
			iv = 0
			# No alpha support; filter for now.
			for v in decs[:3]:
				iv = iv << 8
				iv += min(255, v)
	elif s[offset:].isdigit():
		try:
			iv = int(s[offset:], default)
		except Exception:
			iv = None
	else:
		try:
			iv = int(s, default)
		except Exception:
			iv = None

	return sign, iv

class Status(object):
	"""
	# Editor status annotation.
	"""

	@property
	def selections(self):
		return ()

	rotate = rotate
	def __init__(self, title, keyboard, focus):
		self.index = 0
		self.title = title
		self.keyboard = keyboard
		self.focus = focus

	def close(self):
		pass

	@property
	def position(self):
		return (x.get() for x in self.focus)

	@property
	def mode(self):
		return self.keyboard.current[0]

	def update(self, line, structure):
		pass

	def image(self):
		yield ('title', self.mode)
		l, o = self.position
		yield ('inclusion-space', ' ')
		yield ('inclusion-identifier', f"L{l+1}.{o}")

class Preview(object):
	"""
	# Adapter annotation providing a view of the horizontal range.

	# Previews work exclusively with the horizontal range. When a change is seen,
	# the range is taken from the updated line and given to &convert for building
	# the new status that &tokenize uses to construct the image fragment that
	# is rendered to the view.

	# [ Elements ]
	# /context/
		# Context object given to &tokenize.
	# /selections/
		# Sequence of instance specific constants selected by &index
		# and uncondtionally given to the configured &tokenize function.
	# /convert/
		# Function used to interpret the horizontal range of the current line.
	# /tokenize/
		# Function used to build the image fragments representing the range.
	"""

	selections: Sequence[object]
	context: object
	convert: object
	tokenize: object
	index: int
	title: str

	@classmethod
	def reference(Class, convert, tokenize, context=None, selections=[None], title='', index=0):
		"""
		# Build a reference to an instance.
		"""

		return functools.partial(Class,
			context, selections,
			convert, tokenize,
			# Required per-refraction Position vector.
			title=title,
			index=index,
		)

	rotate = rotate
	def __init__(self, context, selections, convert, tokenize, horizontal, title='', index=0):
		self.selections = selections
		self.context = context
		self.convert = convert
		self.tokenize = tokenize
		self.title = title
		self.index = index
		self.status = (None, None)

		# Refraction state.
		self.horizontal = horizontal

	def close(self):
		pass

	def update(self, line, structure):
		status = line[self.horizontal.slice()]
		if self.status[0] != status:
			self.status = (status, *self.convert(status))

	def image(self):
		try:
			yield from self.tokenize(self.context, self.selections[self.index], *self.status)
		except Exception as error:
			yield ('error-condition', '-')

	def insertion(self):
		return ''.join(x[1] for x in self.image())

color_samples = [
	"\u2588" * 3,
	"<Text Sample>",
	"\u2593" * 3,
	"\u2592" * 3,
	"\u2591" * 3,
	"\u2599\u259f",
]

def color_variant(ctx, variant, src, sign, integer, *, rp=format.RenderParameters.default):
	"""
	# Apply the interpreted integer as the text color of the &variant.
	"""

	return [(rp.apply(cellcolor=0, textcolor=integer), variant)]

# Color preview constructor.
ColorAnnotation = Preview.reference(
	integer_value,
	color_variant,
	selections=color_samples,
)

codepoint_representations = [
	('utf-8', (lambda x: x.encode('utf-8', errors='surrogateescape'))),
]

def codepoint_tokenize(ctx, v, src, string):
	return [('literal-words', repr(v[1](string))[2:-1])]

CodepointAnnotation = Preview.reference(
	(lambda x: (x,)),
	codepoint_tokenize,
	selections=codepoint_representations,
)

integer_representations = [
	('hexadecimal', hex),
	('binary', bin),
	('octal', oct),
	('decimal', str),
	('glyph', chr),
]

def number_tokenize(ctx, v, src, sign, i):
	return [('literal-words', v[1](i))]

BaseAnnotation = Preview.reference(
	integer_value,
	number_tokenize,
	selections=integer_representations,
)

class Directory(object):
	"""
	# Directory query annotation.

	# Provides common features for completion support.
	"""

	@property
	def selections(self):
		# For &rotate.
		return self.matches

	rotate = rotate
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
