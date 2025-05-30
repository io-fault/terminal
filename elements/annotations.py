"""
# Refraction cursor annotations for completion support and ephemeral information displays.
"""
from os.path import islink
import functools
from typing import Sequence

from fault.system import files
from . import types

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

	yield ('field-annotation-start', '(')
	yield from ai.image()
	if ai.title:
		yield ('field-annotation-separator', ' ')
		yield ('field-annotation-title', ai.title)
	yield ('field-annotation-stop', ')')

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
		yield ('inclusion-identifier', f"L{l+1}.{o+1}")

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
	"   ", # Triggers cellcolor.
	"\u2588" * 3,
	"<Text Sample>",
	"\u2593" * 3,
	"\u2592" * 3,
	"\u2591" * 3,
	"\u2599\u259f",
]

def color_variant(ctx, variant, src, sign, integer):
	"""
	# Apply the interpreted integer as the text color of the &variant.
	"""

	if variant.isspace():
		return [(types.Glyph(textcolor=0x000000, cellcolor=integer), variant)]
	else:
		return [(types.Glyph(cellcolor=0x000000, textcolor=integer), variant)]

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
			y.identifier if y.fs_type() != 'directory' else y.identifier + '/'
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

	@staticmethod
	def typed_path_fields(root, extension, *, separator='/'):
		"""
		# Format the path components in &extension relative to &root.
		"""

		current = root
		for f in extension[:-1]:
			if not f:
				yield ('path-empty', '')
			else:
				current = current/f

				if f in {'.', '..'}:
					yield ('relatives', f)
				else:
					if islink(current):
						yield ('path-link', f)
					else:
						try:
							typ = current.fs_type()
						except OSError:
							typ = 'warning'

						if typ == 'directory':
							yield ('path-directory', f)
						elif typ == 'void':
							yield ('file-not-found', f)
						else:
							yield (typ, f)

			yield ('path-separator', separator)

		f = extension[-1]
		final = current/f
		try:
			typ = final.fs_type()
		except OSError:
			typ = 'warning'

		# Slightly different from path segments.
		if typ == 'data':
			try:
				if final.fs_executable():
					typ = 'executable'
				elif f[:1] == '.':
					typ = 'dot-file'
				else:
					# No subtype override.
					pass
			except OSError:
				typ = 'warning'
		elif typ == 'void':
			typ = 'file-not-found'
		else:
			# No adjustments necessary.
			pass

		yield (typ, f)

	def __init__(self, title, lf, source, vertical, horizontal):
		super().__init__(title)
		self.forms = lf
		self.source = source
		self.vertical = vertical
		self.horizontal = horizontal

	def structure_path(self, match):
		# Only displaying the match's filename.
		return self.typed_path_fields(self.location, match.split('/'), separator='/')

	def chdir(self, context, location):
		super().chdir(context, location)
		self.snapshot = list(self.location.fs_iterfiles())

	def update(self, line, structure):
		# Presumes resource location editing.
		ln = self.vertical.get()
		if ln == 0 or self.source.ln_count() < 2:
			rpath = files.root
		else:
			ln_ctx, ln_file = self.source.select(0, 2)

			if ln_file.ln_content.startswith('/'):
				rpath = files.root
			else:
				rpath = (files.root@ln_ctx.ln_content)

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

		status = line[self.start:self.stop]

		# Check for leading path changes.
		if self.location != path:
			# Update &snapshot.
			self.chdir(rpath, path)
			self.select(status)
		elif self.status != status:
			# Update &matches.
			self.select(status)

class ExecutionStatus(object):
	"""
	# Process execution status.
	"""

	from os import kill

	def __init__(self, operation, title, pid, status):
		self.operation = operation
		self.title = title
		self.xs_process_id = pid
		self.xs_data = status

	def close(self):
		if self.xs_data[self.xs_process_id] is None:
			# SIGINT and other signals are not currently accessible.
			try:
				self.kill(self.xs_process_id, 9)
			except ProcessLookupError:
				pass
		else:
			# Exit code already present no clean up necessary.
			del self.xs_data[self.xs_process_id]

	def update(self, line, structure):
		# No response to insertions or deletions.
		pass

	def image(self):
		yield ('inclusion-keyword', self.operation)
		yield ('field-annotation-separator', '[')
		yield ('literal-words', f"{self.xs_process_id}")
		yield ('field-annotation-separator', ']')

	def insertion(self):
		return str(self.xs_process_pid)
