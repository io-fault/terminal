"""
# Refraction cursor annotations for completion support and ephemeral information displays.
"""
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
		ai.index = n - 1

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

	def update(self, li, structure):
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

	def update(self, li, structure):
		status = li.ln_content[self.horizontal.slice()]
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
	def __init__(self, title, system_context, vertical, horizontal):
		self.title = title
		self.system = system_context
		self.vertical = vertical
		self.horizontal = horizontal

		self.close()

	def close(self):
		self.cursor = None
		self.context = None
		self.location = None

		self.status = ""
		self.index = 0

		self.snapshot = []
		self.matches = []

	@staticmethod
	def fs_name_priority(string):
		"""
		# Sort key for the limited sample.
		"""

		c = string[:1]
		if not c:
			return (3, string)

		if c in {'.', '_', '-', '~'}:
			return (1, string)

		if ord(c) < 0x21:
			return (2, string)

		return (0, string)

	@staticmethod
	def fs_snapshot_key(path):
		string = path.identifier
		c = string[:1]
		if not c:
			return (3, string)
		i = ord(c)

		if i > 0x7F:
			return (0, string)

		if i < 0x21:
			# Control characters including space.
			return (2, string)

		if i < 0x41:
			# Puncuations and decimals, Before "A".
			return (1, string)

		if i > 0x5A and i < 0x61:
			return (1, string)

		if i > 0x7A and i <= 0x7F:
			return (1, string)

		return (0, string)

	@staticmethod
	def prompt_field_boundary(lc, co):
		length = len(lc)
		sof = lc.rfind(' ', 0, co)
		if sof == -1:
			sof = 0
		else:
			sof += 1

		if sof < length:
			eof = lc.find(' ', co)
			if eof == -1:
				eof = length

			if lc[sof] == '-':
				# Presume option argument.

				if lc[sof:sof+2] == '--':
					sof = lc.find('=', sof, eof)
					if sof == -1:
						sof = co
						eof = co
					else:
						sof += 1
				else:
					sof += 2
		else:
			eof = length

		return slice(sof, eof)

	def identify_location_context(self, lo, lc, co):
		sys, exe, path = self.system()
		length = len(lc)

		if lo == 0:
			return exe.fs_root, slice(lc.find('/', lc.find('://')+3), length)
		if lc.startswith('/'):
			return exe.fs_root, slice(0, length)

		return exe.fs_root + path, slice(0, length)

	identify_context = identify_location_context

	def identify_prompt_context(self, lo, lc, co):
		sys, exe, path = self.system()
		length = len(lc)

		if lo == 0:
			return exe.fs_root, slice(lc.find('/', lc.find('://')+3), length)

		s = self.prompt_field_boundary(lc, co)
		if lc[s.start:s.start+1] == '/':
			return exe.fs_root, s
		else:
			return exe.fs_root + path, s

	def configure(self, src):
		"""
		# Check the new line for a path context.
		"""

		# Reset state.
		self.close()

		if src.origin.ref_type == 'ivectors':
			self.identify_context = self.identify_prompt_context
		elif src.origin.ref_type == 'location':
			self.identify_context = self.identify_location_context
		else:
			lo = self.vertical.get()
			co = self.horizontal.get()

			self.cursor = types.Cursor.allocate(lo, *self.horizontal.snapshot())
			src.cursors.add(self.cursor)

	def chdir(self, context, location):
		"""
		# Update the &Directory.context and &Directory.location attributes.
		"""

		self.context = context
		self.location = location
		self.snapshot = list(self.location.fs_iterfiles())
		self.snapshot.sort(key=self.fs_snapshot_key)

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

		lead = limit // 2
		for m in self.matches:
			if len(ms) > lead:
				break
			ms.add(m[offset:offset+1])

		# Snapshot sorting moves dot-files and operators to the back.
		for m in reversed(self.matches):
			if len(ms) > limit:
				break
			ms.add(m[offset:offset+1])

		prefixset = sorted(ms, key=self.fs_name_priority)
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

	def structure_path(self, match):
		# Only displaying the match's filename.
		return types.Syntax.typed_path_fields(self.location, match.split('/'), separator='/')

	def path_context_switched(self, cr, lo, co):
		if lo != self.cursor.lines.get():
			# Line changed. Attempt to update path boundaries.
			return True

		if co < cr.start or co > cr.stop:
			# Field changed. Attempt to update path bounardies.
			return True

		# Still editing the same path.
		return False

	def update(self, li, structure):
		# Presumes resource location editing.
		co = self.horizontal.get()

		try:
			if self.cursor is None:
				rpath, cr = self.identify_context(li.ln_offset, li.ln_content, co)
			else:
				if li.ln_offset != self.cursor.lines.get():
					# Keep directory if it's not in the source area.
					return
				sys, exe, path = self.system()
				rpath = exe.fs_root + path
				cr = self.cursor.codepoints.slice()
		except AttributeError:
			# Currently trapped for Process missing fs_root.
			return

		current = co - cr.start
		pattern = li.ln_content[cr]
		prefix = max(0, pattern.rfind('/', 0, current))
		segment = min(cr.stop, pattern.find('/', current))

		# Update location.
		pathstr = pattern[:prefix]
		if pathstr:
			path = +(rpath@pathstr)
		else:
			path = rpath

		status = pattern[prefix:(None if segment == -1 else segment+1)].strip('/')

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

	def update(self, li, structure):
		# No response to insertions or deletions.
		pass

	def image(self):
		yield ('inclusion-keyword', self.operation)
		yield ('field-annotation-separator', '[')
		yield ('literal-words', f"{self.xs_process_id}")
		yield ('field-annotation-separator', ']')

	def insertion(self):
		return str(self.xs_process_pid)
