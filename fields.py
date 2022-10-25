"""
# Field entry management package.
"""

import abc
import operator
import keyword
import itertools
import functools

class Field(metaclass = abc.ABCMeta):
	"""
	# Protocol for Field types.
	"""

	@property
	@abc.abstractmethod
	def empty(self):
		"""
		# Designates that the Field contains no content.
		"""

	@property
	@abc.abstractmethod
	def full(self):
		"""
		# Designates that the field is full and cannot accept inserts.
		"""

	@abc.abstractmethod
	def characters(self):
		"""
		# Number of characters in the field.
		"""

	@abc.abstractmethod
	def cells(self):
		"""
		# Number of cells used by the display of the field.
		"""

	@abc.abstractmethod
	def value(self):
		"""
		# The value of the field or structure.
		"""

	@abc.abstractmethod
	def subfields(self):
		"""
		# The absolute sequence of fields contained within the Field.
		# Nested fields must be unnested by including the Field context.

		# Returns an iterator producing a triple:

			# (path, field)

		# Where path is a tuple containing the sequence of containing fields
		# and the corresponding index:

			# (index, field), ...
		"""

	@abc.abstractmethod
	def count(self):
		"""
		# Number of subfields contained by the field.
		# &None if the field is not a container.
		"""

def changelength(delta):
	"""
	# Calculate the length of a delta.
	"""
	l = 0
	for x in delta:
		if x[0] == 'delete':
			start, stop = x[1]
			l -= (stop - start)
		if x[0] == 'insert':
			l += len(x[1][-1])
	return l

def address(seq, start, stop, len=len, range=range):
	"""
	# Find the address of the absolute slice.
	"""
	start = start or 0
	assert start <= stop
	assert start >= 0
	assert stop >= 0

	sl = len(seq)

	start_index = 0
	position = 0

	# find start
	for i in range(0, sl):
		ilen = len(seq[i])
		position += ilen
		if position >= start:
			# found the position
			start_index = i
			start_index_offset = position - ilen
			break
	else:
		# request beyond the text length
		return ((sl, 0), (sl, 0))
	start_roffset = start - start_index_offset

	# find stop
	position = start_index_offset
	for i in range(start_index, sl):
		ilen = len(seq[i])
		position += ilen
		if position >= stop:
			# found the position
			stop_index = i
			stop_index_offset = position - ilen
			break
	else:
		# stop offset exceeds total length
		stop_index_offset = position - ilen # total string length
		stop_index = sl - 1 # end of sequence

	stop_roffset = stop - stop_index_offset

	# compound slice
	return (
		(start_index, start_roffset),
		(stop_index, stop_roffset),
	)

def delete(seq, start, stop, empty="", len=len, range=range):
	starts, stops = address(seq, start, stop)
	start_index, start_roffset = starts
	stop_index, stop_roffset = stops
	check_merge = None

	sl = len(seq)

	if start_index == stop_index:
		# removing a substring
		s = seq[start_index]
		# overwrite the index
		overwrite = s.__class__(s[:start_roffset] + s[stop_roffset:])
		if overwrite == empty:
			overwrite = empty
		seq[start_index] = overwrite
	else:
		s = seq[start_index]
		overwrite = s.__class__(s[:start_roffset])
		seq[start_index] = overwrite
		if not overwrite:
			# Remove empty entry.
			start_index -= 1
			check_merge = True

		if stop_index < sl:
			# assign stop as well given its inside the seq
			s = seq[stop_index]
			overwrite = s.__class__(s[stop_roffset:])
			seq[stop_index] = overwrite
			if overwrite == empty:
				stop_index += 1
				check_merge = True

		# clear everything between start+1 and stop
		del seq[start_index+1:stop_index]

		if check_merge and seq:
			end = start_index + 2
			pair = seq[start_index:end]
			for x in pair:
				if not getattr(x, 'merge', False):
					break
			else:
				if pair:
					seq[start_index:end] = (pair[0].__class__(''.join(pair)),)
	return seq

def insert(seq, offset, insertion, empty = "", len = len):
	if not insertion:
		return seq

	if offset <= 0:
		# prepend
		if seq and seq[0] == empty:
			seq[0] = insertion
		else:
			seq.insert(0, insertion)
		return seq

	sl = len(seq)

	position = 0
	for i in range(0, sl):
		# scan for the item that contains the offset
		ilen = len(seq[i])
		position += ilen
		if position > offset:
			break
	else:
		# appending
		if seq and seq[-1] == empty:
			seq[-1] = insertion
		else:
			seq.append(insertion)
		return seq

	roffset = offset - (position - ilen)

	if roffset == 0 and seq[i-1] == empty:
		# empty string at position
		# substitute and continue
		seq[i-1] = insertion
		return seq

	# not prepending or appending, so split the sequence and the middle element if any
	# prefix and suffix at position
	suffix = seq[i:]

	if not suffix:
		# empty suffix
		seq.append(insertion)
		return seq

	prefix = seq[:i]

	if roffset == 0:
		# very beginning of suffix, so append to prefix
		prefix.append(insertion)
		prefix.extend(suffix)
	else:
		# roffset > 0, so split suffix[0]

		prefix.append(suffix[0][:roffset])
		prefix.append(insertion)
		suffix[0] = suffix[0][roffset:]

		prefix.extend(suffix)

	return prefix

@Field.register
class String(str):
	"""
	# A constant string field. The contents are immutable and it identifies itself as full.
	"""
	__slots__ = ()
	merge = True

	def __getitem__(self, args):
		return self.__class__(super().__getitem__(args))

	@property
	def empty(self):
		return self == ""

	@property
	def full(self):
		return True

	def count(self):
		return None

	def delete(self, start, stop):
		pass

	def insert(self, position, string):
		pass

	def value(self):
		return str(self)

	def length(self, len = len):
		return len(self)
	characters = str.__len__
	cells = characters

class Constant(String):
	merge = False

class Delimiter(String):
	merge = False

@Field.register
class Styled(object):
	"""
	# Explicitly styled text field.
	"""

	__slots__ = ('text', 'traits', 'textcolor', 'cellcolor', 'linecolor')

	@property
	def underlined(self):
		return 'underline' in self.traits

	def __init__(self, text="", fg=-1024):
		self.text = text
		self.textcolor = fg
		self.cellcolor = -1024
		self.linecolor = -1024
		self.traits = 0

	def terminal(self):
		"""
		# Return a tuple suitable for fault.terminal.
		"""

		return (
			self.text,
			self.traits,
			self.textcolor,
			self.cellcolor,
			self.linecolor,
		)

@Field.register
class Text(object):
	"""
	# Mutable string field.

	# Normally subclassed for specific languages for highlighting.
	"""

	__slots__ = ('sequences',)

	empty_entry = String("")
	constants = ()
	classifications = ()

	@property
	def empty(self):
		return len(self) == 0

	@property
	def full(self):
		"""
		# Whether or not more characters can be inserted.
		"""
		if self.limit is None:
			return False
		return len(self) < self.limit

	def characters(self):
		return len(self)

	def __init__(self, string = String("")):
		self.sequences = [string]

	@classmethod
	def from_sequence(Class, sequence):
		r = Class.__new__(Class)
		r.sequences = sequence
		return r

	def set(self, characters):
		"""
		# Set the field characters. Used loading fields.
		# Destroys the log (delta sequence).
		"""
		inverse = (self.set, (self.sequences,))
		self.sequences = characters
		return inverse

	def clear(self):
		"""
		# Set the text to an empty string.
		"""
		return self.set([self.empty_entry])

	def insert(self, offset, string, op=insert, len=len):
		strlen = len(string)
		self.sequences = op(self.sequences, offset, string, empty = self.empty_entry)
		end = offset + strlen

		# consolidate the insert into the former or the latter field
		if not isinstance(string, Field):
			self.reformat()
		elif string.merge:
			seq = self.sequences
			seqlen = len(seq)
			Class = string.__class__

			start, stop = address(seq, offset, end)

			start_index, start_roffset = start
			if len(seq[start_index]) == start_roffset:
				start_index += 1
				start_roffset = 0

			jstart = start_index
			jstop = start_index + 1

			for jstart in range(start_index, -1, -1):
				item = seq[jstart]
				if item.merge == False:
					jstart += 1
					break

			for jstop in range(start_index, seqlen):
				item = seq[jstop]
				if item.merge == False:
					break
			else:
				jstop = seqlen

			replace = Class("".join(seq[jstart:jstop]))
			del seq[jstart:jstop]
			seq.insert(jstart, replace)

		return (self.delete, (offset, end))

	def delete(self, start, stop):
		# normalize and restrict slice size as needed.
		global delete

		l = len(self)
		stop = max(stop, 0)
		start = max(start, 0)
		if stop > l:
			stop = l
		if start > l:
			start = l
		if start > stop:
			l = start
			start = stop
			stop = l

		section = str(self)[start:stop]

		self.sequences = delete(self.sequences, start, stop, empty = self.empty_entry)

		return (self.insert, (start, section))

	def replace(self, start, stop, string):
		di = self.delete(start, stop)
		ii = self.insert(start, string)
		return [di, ii]

	def __len__(self):
		return sum(map(len, self.sequences))
	length = __len__

	def count(self):
		return len(self.sequences)

	def value(self):
		return ''.join(self.sequences)

	def subfields(self, path = ()):
		return zip(((self, i) for i in range(len(self.sequences))), self.sequences)

	def __str__(self):
		return ''.join(map(str, self.sequences))

	def __repr__(self):
		return repr(self.sequences)

class Line(Text):
	"""
	# Text object representing a single line.
	# Implies the special handling of control characters.
	"""
	__slots__ = Text.__slots__

class FieldSeparator(Delimiter):
	"""
	# A space-like character used to delimit fields for commands.

	# Primarily used by Prompts to distinguish between spaces and field separation.
	"""
	__slots__ = Delimiter.__slots__
	classifications = ()

field_separator = FieldSeparator(':')

@Field.register
class Formatting(int):
	"""
	# A field that represents a sequence of tabs.
	# Cannot be used inside &Text fields.
	"""

	__slots__ = ()

	character = ''
	identity = 'empty'
	size = 0

	@property
	def empty(self):
		return self.length() == 0

	@property
	def full(self):
		return True

	def characters(self):
		return self * self.size
	cells = characters

	def count(self):
		return None

	def insert(self, *args):
		return None

	def delete(self, *args):
		return None

	def __str__(self):
		return self.character * (self * self.size)

	def __len__(self):
		return self.size * self

	def value(self):
		return self.character * self

	def length(self):
		return self * self.size
	characters = length

class Spacing(Formatting):
	"""
	# A field that represents a series of spaces.
	"""

	__slots__ = ()

	character = ' '
	identity = 'space'
	size = 1

class Indentation(Formatting):
	"""
	# A field that represents a series of tabs.
	"""
	__slots__ = ()
	character = '\t'
	identity = 'tab'
	size = 4

	@classmethod
	@functools.lru_cache(16)
	def acquire(Class, level):
		return Class(level)

class Terminator(Formatting):
	"""
	# A field that represents a newline.
	"""
	__slots__ = ()
	character = '\n'
	identity = 'newline'
	size = 1

@Field.register
class Sequence(list):
	__slots__ = ()

	# Surrounding field content for disambiguating
	# field selection.
	field_usage_indicators = {
		'key': ("<", ">"),
		'': ("(", ")"),
		'value': ("[", "]"),
		'item': ("<", ">"),
		'expression': ("{", "}"),
		'default': ("[", "]"),
	}

	# dict:
	# <key> [value]
	# <key> [value]
	# <key> [value]
	# matrix:
	#  |item| |item| |item|
	#  |item| |item| |item|
	#  |item| |item| |item|
	# list:
	#  [item] [item]

	@property
	def empty(self):
		"""
		# Whether the sequence contains non-empty fields.
		"""
		for x in self:
			if not x.empty:
				return False
		return True

	def count(self):
		"""
		# The number of fields immediately contained.
		"""
		return len(self)

	def prefix(self, *fields):
		self[0:0] = fields

	def suffix(self, *fields):
		self.extend(fields)

	def insert(self, position, *fields):
		self[position:position] = fields
		return (self.delete, fields)

	def insertion(self, seq):
		sinsert = super().insert
		for p, f in seq:
			sinsert(p, f)

		return (self.delete, [x[1] for x in seq])

	def delete(self, *fields, get0=operator.itemgetter(0)):
		"""
		# Delete a set of fields from the sequence.
		"""
		indexes = list(map(self.index, fields))
		index_fields = list(zip(indexes, fields))
		index_fields.sort(key = get0)

		for i, f in reversed(index_fields):
			del self[i]

		return (self.insertion, index_fields)

	def clear(self):
		inverse = (self.extend, self[:])
		super().clear()
		return inverse

	def __str__(self):
		"""
		# Display string of the sequence of fields.
		"""
		return ''.join(map(str, self.value()))

	def length(self, lenmethod=operator.methodcaller('length')):
		"""
		# The sum of the *display* length of the contained fields.
		"""
		return sum(map(lenmethod, self))
	characters = length

	def cells(self, lenmethod=operator.methodcaller('cells')):
		"""
		# Sum of &cells of all the subfields.
		"""
		return sum(map(lenmethod, self))

	def subfields(self, path=(), range=range, len=len, isinstance=isinstance):
		"""
		# Map the nested sequences into a serialized form.

		# The tuples produced are pairs containing the field and path to the field.
		# The path being the sequence of sequences containing the field.
		"""

		if self in path:
			# recursive
			raise Exception('recursive fields')

		for i in range(len(self)):
			x = self[i]
			if isinstance(x, (self.__class__, Text)):
				yield from x.subfields(path + ((self, i),))
			else:
				yield (path + ((self, i),), x)

	def value(self):
		for path, x in self.subfields():
			yield x.value()

	def offset(self, path, field):
		"""
		# Get the horizontal positioning of the field within the unit.
		"""
		offset = 0

		for upath, ufield in self.subfields():
			if ufield == field and upath == path:
				# found the filed
				break
			offset += ufield.length()
		else:
			return None

		return offset

	def find(self, offset, state = None):
		"""
		# Find the field at the relative offset.

		# If the offset is beyond the end of the sequence, &None.
		# If the offset is less than zero, the first.
		"""
		if self.empty:
			return ((), self, (0, 0, ()))

		path = None
		field = None

		if state is None:
			i = iter(self.subfields())
			current = 0
			l = 0
		else:
			current, l, i = state
			current += l

		for path, field in i:
			l = field.length()
			if offset - l < current:
				return (path, field, (current, l, i))
			current += l
		else:
			current -= l

		# offset is beyond edge, so select last
		return (path, field, (current, l, i))

space = Delimiter(" ")
