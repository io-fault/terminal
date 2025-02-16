"""
# Implementations for user interface elements.
"""
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional
import collections
import itertools
import weakref

from fault.context import tools
from fault.system import files
from fault.system.query import home

from . import symbols
from . import location
from . import annotations
from . import alignment
from . import types
from . import sequence
from . import delta
from . import ia
from . import types
from . import fields

from .types import Model, View, Reference, Area, Glyph, Device, System

class Core(object):
	"""
	# Common properties and features.

	# Currently, only used to identify a user interface element.
	"""

class Execution(Core):
	"""
	# System process execution status and interface.

	# [ Elements ]
	# /identity/
		# The identity of the system that operations are dispatched on.
		# The object that is used to identify an &Execution instance within a &Session.
	# /encoding/
		# The encoding to use for environment variables and argument vectors.
		# This may *not* be consistent with the preferred filesystem encoding.
	# /environment/
		# The set of environment variables needed when performing operations
		# *within* the system context.
		# Only when host execution is being performed will this be the set of
		# environment variables passed into the Invocation.
	# /executable/
		# The host local, absolute, filesystem path to the executable
		# used by &interface.
	# /interface/
		# The local system command, argument vector, to use to dispatch
		# operations in the system context.
	"""

	identity: System

	encoding: str
	executable: str
	interface: Sequence[str]
	environment: Mapping[str, str]

	def __str__(self):
		return ''.join(x[1] for x in self.i_status())

	def i_status(self):
		yield from self.identity.i_format(self.pwd())

	def export(self, kv_iter:Iterable[tuple[str,str]]):
		"""
		# Update the environment variables present when execution is performed.
		"""

		self.environment.update(kv_iter)

	def getenv(self, name) -> str:
		"""
		# Return the locally configured environment variable identified by &name.
		"""

		return self.environment[name]

	def setenv(self, name, value):
		"""
		# Locally configure the environment variable identified by &name to &value.
		"""

		self.environment[name] = value

	def pwd(self):
		"""
		# Return the value of the locally configured (system/environ)`PWD`.
		"""

		return self.environment['PWD']

	def chdir(self, path: str, *, default=None) -> str|None:
		"""
		# Locally set (system/environ)`PWD` and return the old value or &default if unset.
		"""

		current = self.environment.get('PWD', default)
		self.environment['PWD'] = path
		return current

	def __init__(self, identity:System, encoding, ifpath, argv):
		self.identity = identity
		self.environment = {}
		self.encoding = encoding
		self.executable = ifpath
		self.interface = argv

##
# The line content offset is hardcoded to avoid references, but are
# parenthesized so that substitution may be performed if changes are needed.
class Resource(Core):
	"""
	# The representation of a stored resource and its modifications.

	# This is not intended to be a projection of the resource identified by &origin.
	# It is the record set that represents the content of the resource read
	# from the system. Interfaces for loading and storing the resource on disk are managed
	# primarily by the session.

	# [ Elements ]
	# /origin/
		# Reference identifying the resource being modified and refracted.
	# /forms/
		# The default line reformulations for formatting the elements.
	# /elements/
		# The sequence of lines being modified.
	# /modifications/
		# The log of changes applied to &elements.
	# /cursors/
		# The collection of cursors tracking changes to the resource.
	"""

	origin: types.Reference
	forms: types.Reformulations

	elements: Sequence[str]
	modifications: delta.Log

	status: object
	cursors: Mapping[types.Position, types.Position]

	def __init__(self, origin, forms):
		self.origin = origin
		self.forms = forms

		self.elements = sequence.Segments([])
		self.modifications = delta.Log()
		self.snapshot = self.modifications.snapshot()
		self.status = None
		self.cursors = {}

	def ln_count(self) -> int:
		"""
		# The current number of lines present in the document.
		"""

		return self.elements.__len__()

	def sole(self, line_offset:int) -> types.Line:
		"""
		# Retrieve the &types.Line instance for the given &line_offset.
		"""

		return self.forms.ln_structure(self.elements[line_offset], line_offset)

	def select(self, start, stop) -> Iterable[types.Line]:
		"""
		# Retrieve &types.Line instances in the given range defined
		# by &start and &stop.
		"""

		if stop < start:
			sign = -1
		else:
			sign = +1

		structure = self.forms.ln_structure
		i = start
		for li in self.elements.select(start, stop):
			yield structure(li, ln_offset=i)
			i += sign

	def serialize(self, start:int, stop:int, encoding=None) -> Iterable[bytes]:
		"""
		# Convert lines between &start and &stop into the
		# encoded form described by &forms.
		"""

		lfb = self.forms.lf_codec
		lfl = self.forms.lf_lines
		lines = ((li.ln_level, li.ln_content) for li in self.select(start, stop))
		return lfb.sequence(lfl.sequence(lines))

	@staticmethod
	def since(start, stop, *, precision='millisecond'):
		m = start.measure(stop).truncate(precision)

		D = m.select('day')
		m = m.decrease(day=D)
		H = m.select('hour')
		m = m.decrease(hour=H)
		M = m.select('minute')
		m = m.decrease(minute=M)
		S = m.select('second')
		P = m.decrease(second=S).select(precision)

		return (D, H, M, S, P)

	@property
	def last_modified(self):
		"""
		# When the resource was last modified.
		"""

		return self.status.last_modified

	def age(self, when) -> str:
		"""
		# Format a string identifying how long it has been since the resource was last changed.
		"""

		D, H, M, S, MS = self.since(self.last_modified, when)

		fmt = [
			f"{c} {unit}" for (c, unit) in zip(
				[D, H, M],
				['days', 'hours', 'minutes']
			)
			if c > 0
		]
		fmt.append(f"{S}.{MS:03} seconds")

		return ' '.join(fmt)

	def last_insertion(self, limit=8, islice=itertools.islice):
		"""
		# Retrieve the last insertion from the log.
		"""

		for r in islice(reversed(self.modifications.records), 0, limit):
			last = r.insertion
			if last:
				return last

		return ""

	def version(self):
		"""
		# Get the identifier of the latest modification.
		"""

		return self.modifications.snapshot()

	def changes(self, version):
		"""
		# Get the &delta instructions since the given &version.
		"""

		return self.modifications.since(version)

	def undo(self, quantity=1):
		"""
		# Revert modifications until the previous checkpoint is reached.
		"""

		return self.modifications.undo(self.elements, quantity)

	def redo(self, quantity=1):
		"""
		# Replay modifications until the next checkpoint is reached.
		"""

		return self.modifications.redo(self.elements, quantity)

	def commit(self, collapse=True):
		"""
		# Apply pending modifications.
		"""

		log = self.modifications.apply(self.elements)
		if collapse:
			log.collapse()
		return log.commit()

	def checkpoint(self, collapse=True):
		"""
		# Apply, commit, and checkpoint the log.
		"""

		log = self.modifications.apply(self.elements)
		if collapse:
			log.collapse()
		return log.commit().checkpoint()

	def insert_codepoints(self, lo, offset, string):
		"""
		# Insert the &string at the given &offset without committing or applying.
		"""

		return (self.modifications
			.write(delta.Update(lo, string, "", offset + (4))))

	def extend_codepoints(self, lo, string):
		"""
		# Append the given &string to the line, &lo.
		"""

		co = self.sole(lo).ln_length + (4)

		(self.modifications
			.write(delta.Update(lo, string, "", co)))

	def delete_codepoints(self, lo:int, start:int, stop:int):
		"""
		# Remove &deletion from the &offset in line &lo.

		# [ Parameters ]
		# /lo/
			# The line offset containing the codepoints to be deleted.
		# /start/
			# The codepoint offset to delete from.
		# /stop/
			# The codepoint offset to delete to.

		# [ Returns ]
		# The given &deletion.
		"""

		line = self.elements[lo]
		start += (4)
		stop += (4)
		deletion = line[start:stop]

		(self.modifications
			.write(delta.Update(lo, "", deletion, start)))

		return deletion

	def substitute_codepoints(self, lo:int, start:int, stop:int, string:str) -> int:
		"""
		# Remove the horizontal range from the line identified by &lo and
		# insert the &string at &start.

		# [ Returns ]
		# The actual change in size.
		"""

		deletion = self.delete_codepoints(lo, start, stop)
		self.insert_codepoints(lo, start, string)

		return deletion

	def increase_indentation(self, lo:int, change:int):
		"""
		# Unconditionally apply the given &change to the indentation
		# level of the line at &lo.
		"""

		log = self.modifications
		li = self.sole(lo)
		i = li.ln_level + change
		log.write(delta.Update(li.ln_offset, chr(i), chr(li.ln_level), 0))

	def adjust_indentation(self, start:int, stop:int, change:int):
		"""
		# Apply the given &change to the indentation of the lines within
		# &start and &stop while skipping lines with no content and no
		# indentation.
		"""

		log = self.modifications
		for li in self.select(start, stop):
			if li.ln_void:
				continue

			i = max(0, li.ln_level + change)
			log.write(delta.Update(li.ln_offset, chr(i), chr(li.ln_level), 0))

	def delete_indentation(self, start:int, stop:int):
		"""
		# Remove all indentations from all the lines in &start and &stop.
		"""

		log = self.modifications
		zero = chr(0)

		for li in self.select(start, stop):
			if li.ln_level == 0:
				continue
			log.write(delta.Update(li.ln_offset, zero, chr(li.ln_level), 0))

	def join(self, lo, count, *, withstring=''):
		"""
		# Join &count lines onto &lo using &withstring.

		# [ Parameters ]
		# /lo/
			# The line offset.
		# /count/
			# The number of lines after &lo to join.
		# /withstring/
			# The character placed between the joined lines.
			# Defaults to an empty string.
		"""

		lines = list(self.select(lo, lo+1+count))
		combined = withstring.join(li.ln_content for li in lines)

		(self.modifications
			.write(delta.Update(lo, combined, self.elements[lo][4:], (4)))
			.write(delta.Lines(lo+1, [], [self.elements[lo+1]])))

		return (lo+1, -len(lines))

	def split(self, lo, offset):
		"""
		# Split the line identified by &lo at &offset.
		"""

		lf = self.forms
		li = self.sole(lo)
		nlstr = li.ln_content[offset:]
		nl = lf.ln_interpret(nlstr, level=li.ln_level)

		(self.modifications
			.write(delta.Update(lo, "", nlstr, offset + (4)))
			.write(delta.Lines(lo+1, [lf.ln_sequence(nl)], [])))

		return (lo, 2)

	def splice_text(self, ln_format, lo:int, co:int, text:str, ln_level=0):
		"""
		# Insert &text in the line &lo at the indentation relative character &co.
		# Using &ln_format to split lines in &text, the first line is inserted
		# before &co in &lo. The trailing lines are inserted after &lo with the last line
		# inheriting any text *after* &co.

		# [ Parameters ]
		# /ln_format/
			# The line form that should be used to split &text.
		# /lo/
			# The line offset in &self.elements.
		# /co/
			# The codepoint offset in the target line, &lo.
		# /text/
			# The text to be split and integrated into &self.elements.
		# /ln_level/
			# The indentation level to add to all created lines.

		# [ Returns ]
		# The insertion state as a tuple holding the line offset, codepoint offset,
		# and remainder to be prefixed to text for the next call to splice_text.
		"""

		# Check for partial termination.
		# No-op for single byte termination.
		pt = ln_format.measure_partial_termination(text)
		if pt:
			# Avoid inserting codepoints that may become a boundary
			# with the next insertion.
			remainder = text[-pt:]
			text = text[:-pt]
		else:
			remainder = ''

		first, *wholes = text.split(ln_format.termination)

		level_line = ln_format.level
		target_line = self.sole(lo)

		# Handle indentation extension case. Previous splice has a partial
		# read on an indented, currently, content-less line. When this happens,
		# indentation needs to be increased when flevel is greater than zero.
		flevel, fcontent = level_line(first)
		if flevel:
			if not target_line.ln_content or co == 0:
				# Inherit leading indentation.
				self.increase_indentation(lo, flevel)
			else:
				# Indentation already terminated, line content has already began.
				# Insert indentation codepoints raw.
				fcontent = first

		if wholes:
			# Carry the tail in the first line.
			suffix = self.substitute_codepoints(lo, co, target_line.ln_length, fcontent)
			wholes[-1] = wholes[-1] + suffix

			# Identify indentation boundaries and structure the line.
			ln_i = self.forms.ln_interpret # Universal
			llines = map(level_line, wholes)
			slines = list(ln_i(ls, level=(ln_level+il if ls else il)) for il, ls in llines)

			# Insert and identify the new codepoint offset in the final line.
			dl = self.insert_lines(lo+1, slines)
			co = slines[-1].ln_length - len(suffix)
		else:
			self.insert_codepoints(lo, co, fcontent)
			co = co + len(fcontent)
			dl = 0 # No change in &lo.

		return (lo + dl, co, remainder)

	def replicate_lines(self, lo:int, start:int, stop:int):
		"""
		# Copy the lines between &start and &stop to &lo.
		"""

		rlines = self.elements[start:stop]
		(self.modifications
			.write(delta.Lines(lo, rlines, [])))

		return len(rlines)

	def delete_lines(self, start:int, stop:int):
		"""
		# Remove the lines in the range &start and &stop.

		# [ Returns ]
		# The lines removed.
		"""

		lines = self.elements[start:stop]

		(self.modifications
			.write(delta.Lines(start, [], lines)))

		# Export in generator to defer processing in case discarded.
		return len(lines)

	def insert_lines(self, lo, lines:Iterable[types.Line]):
		"""
		# Insert the &lines before &lo.
		"""

		slines = [self.forms.ln_sequence(x) for x in lines]
		(self.modifications
			.write(delta.Lines(lo, slines, [])))

		return len(slines)

	def extend_lines(self, lines:Iterable[types.Line]):
		"""
		# Append the given &lines to the resource's elements.
		"""

		slines = [self.forms.ln_sequence(x) for x in lines]
		(self.modifications
			.write(delta.Lines(self.ln_count(), slines, []))
		)

		return len(slines)

	def ln_initialize(self, content="", level=0, offset=None):
		"""
		# Initialize a new line at the end of elements.
		"""

		lo = offset if offset is not None else self.ln_count()
		lines = [chr(level) + "\x00\x00\x00" + content]
		(self.modifications
			.write(delta.Lines(lo, lines, []))
		)

	def swap_case(self, lo:int, start:int, stop:int):
		"""
		# Swap the case of the character unit under the cursor.
		"""

		start += (4)
		stop += (4)

		lc = self.elements[lo]
		subbed = lc[start:stop]

		(self.modifications
			.write(delta.Update(lo, subbed.swapcase(), subbed, start)))

	def move_lines(self, lo:int, start:int, stop:int) -> int:
		"""
		# Relocate the vertical range identified by &start and &stop before
		# the line identified by &lo.

		# [ Returns ]
		# The actual count of lines moved.
		"""

		# Potentially effects update alignment.
		# When a move is performed, update only looks at the final
		# view and elements state. If insertion is performed before
		# delete, the final state will not be aligned and the wrong
		# elements will be represented at the insertion point.
		log = self.modifications.write
		deletion = self.elements[start:stop]

		if start < lo:
			# Deleted range comes before insertion line.
			log(delta.Lines(start, [], deletion))
			log(delta.Lines(lo - len(deletion), deletion, []))
		else:
			# Deleted range comes after insertion line.
			assert lo <= start

			log(delta.Lines(start, [], deletion))
			log(delta.Lines(lo, deletion, []))

		return len(deletion)

	def take_leading(self, lo:int, co:int) -> str:
		"""
		# Delete and return the codepoints *before* &co in the line, &lo.

		# [ Parameters ]
		# /lo/
			# The offset of the line to edit.
		# /co/
			# The codepoint offset to delete from.
		"""

		lf = self.forms
		r = self.elements[lo][(4):co+(4)]

		if r:
			(self.modifications
				.write(delta.Update(lo, "", r, (4))))

		return r

	def take_following(self, lo:int, co:int) -> str:
		"""
		# Delete and return the codepoints *after* &co in the line, &lo.

		# [ Parameters ]
		# /lo/
			# The offset of the line to edit.
		# /co/
			# The codepoint offset to delete from.
		"""

		lf = self.forms
		r = self.sole(lo).ln_content[co:]

		if r:
			(self.modifications
				.write(delta.Update(lo, "", r, co + (4))))

		return r

	def map_contiguous_block(self, il, start, stop):
		"""
		# Identify the area of non-empty lines.
		"""

		bstart = 0
		bstop = self.ln_count()

		for ln in self.select(stop, bstop):
			if ln.ln_void:
				bstop = ln.ln_offset
				break

		for ln in self.select(start-1, -1):
			if ln.ln_void:
				bstart = ln.ln_offset + 1
				break

		return (bstart, bstop)

	def map_indentation_block(self, il, start, stop):
		"""
		# Identify the area of an indentation level.
		"""

		bstart = 0
		bstop = self.ln_count()

		if il == 0:
			return (bstart, bstop)

		for ln in self.select(stop, bstop):
			if ln.ln_content and ln.ln_level < il:
				bstop = ln.ln_offset
				break

		for ln in self.select(start, -1):
			if ln.ln_content and ln.ln_level < il:
				bstart = ln.ln_offset + 1
				break

		return (bstart, bstop)

	def indentation_enclosure_footing(self, il, lo):
		"""
		# Identify the area of the header and footer of an indentation level.
		"""

		# Scan forwards for reduced IL with content.
		eof = self.ln_count()
		ilines = iter(self.select(lo, eof))

		leading_void = self.sole(lo - 1).ln_void

		# Scan for IL reduction.
		for ln in ilines:
			if ln.ln_level < il:
				# Found reduction in IL, note last exclusive.

				if leading_void and ln.ln_offset == lo:
					# Handle Python's case where there is no footing.
					return lo

				il = ln.ln_level
				last = ln.ln_offset
				break
		else:
			return eof

		# Scan for contiguous lines at the reduced IL.
		for ln in ilines:
			if ln.ln_level >= il and ln.ln_content:
				# Continue while there is a contiguous block at the reduced IL.
				continue
			else:
				# IL reduced or void.
				if ln.ln_void:
					# Seek end of void.
					break
				else:
					# Reduced IL with content.
					return ln.ln_offset
		else:
			return eof

		# Scan for contiguous void lines.
		for ln in ilines:
			if not ln.ln_void:
				# Scanned past all contiguous lines.
				return ln.ln_offset

		return eof

	def indentation_enclosure_heading(self, il, lo):
		"""
		# Identify the area of the header of an indentation level.
		"""

		eof = self.ln_count()

		# Scan forwards for reduced IL with content.
		ilines = iter(self.select(lo - 1, -1))

		# Scan for IL reduction.
		for ln in ilines:
			if ln.ln_level < il:
				# Found reduction in IL, note last exclusive.
				il = ln.ln_level
				break
		else:
			return 0

		# Scan for contiguous lines at the reduced IL.
		for ln in ilines:
			if ln.ln_level >= il and ln.ln_content:
				# Continue while there is a contiguous block at the reduced IL.
				continue
			else:
				return ln.ln_offset + 1

		return 0

	def find_indentation_block(self, il, lo, limit=0):
		"""
		# Identify the area of an adjacent indentation level.
		"""

		# Find the indentation.
		for ln in self.select(lo, limit):
			if not ln.ln_void and ln.ln_level == il:
				# Detect the edges.
				return self.map_indentation_block(il, ln.ln_offset, ln.ln_offset)

		return None

	def find_next_void(self, lo:int) -> types.Line:
		"""
		# Find the next completely empty line from &lo.
		"""

		for ln in self.select(lo, self.ln_count()):
			if ln.ln_void:
				return ln

		return None

	def find_previous_void(self, lo:int) -> types.Line:
		"""
		# Find the previous completely empty line from &lo.
		"""

		for ln in self.select(lo, -1):
			if ln.ln_void:
				return ln

		return None

class Refraction(Core):
	"""
	# The elements and status of a selected resource.

	# [ Elements ]
	# /source/
		# The resource providing the lines to display and manipulate.
	# /annotation/
		# Cursor annotation state.
	# /focus/
		# The cursor selecting an element.
		# A path identifying the ranges and targets of each dimension.
	# /limits/
		# Per dimension offsets used to trigger margin scrolls.
		# XXX: Merge into visibility and use Position again.
	# /visible/
		# The first elements visible in the view for each dimension.
	# /activate/
		# Action associated with return and enter.
		# Defaults to &None.
		# &.ia.types.Selection intercepts will eliminate the need for this.
	# /system_execution_status/
		# Status of system processes executed by commands targeting the instance.
	"""

	source: Resource
	annotation: Optional[types.Annotation]
	focus: Sequence[object]
	limits: Sequence[int]
	visible: Sequence[int]
	activate = None
	cancel = None

	def current(self, depth):
		d = self.source.elements
		for i in range(depth):
			f = self.focus[i]
			fi = f.get()
			if fi < len(d):
				d = d[f.get()]
			else:
				return ""
		return d or ""

	def annotate(self, annotation):
		"""
		# Assign the given &annotation to the refraction after closing
		# and deleting any currently configured annotation.
		"""

		if self.annotation is not None:
			self.annotation.close()

		self.annotation = annotation

	def retype(self, lf:types.Reformulations):
		"""
		# Reconstruct &self with a new syntax type.
		"""

		new = object.__new__(self.__class__)
		new.__dict__.update(self.__dict__.items())
		new.forms = lf
		return new

	def __init__(self, resource):
		self.source = resource
		self.forms = resource.forms
		self.annotation = None
		self.system_execution_status = {}

		self.focus = (types.Position(), types.Position())
		self.visibility = (types.Position(), types.Position())
		self.query = {} # Query state; last search, seek, etc.
		# View related state.
		self.dimensions = None
		self.limits = (0, 0)
		self.visible = [0, 0]

	def configure(self, dimensions):
		"""
		# Configure the refraction for a display connection at the given dimensions.
		"""

		vv, hv = self.visibility
		width = dimensions.span
		height = dimensions.lines

		vv.magnitude = height
		hv.magnitdue = width
		vv.offset = min(12, height // 12) or -1 # Vertical, align with elements.
		hv.offset = min(6, width // 20) or -1

		self.limits = (vv.offset, hv.offset)
		self.dimensions = dimensions

		return self

	def view(self):
		return self.source.ln_count(), self.dimensions[1], self.visible[1]

	def scroll(self, delta):
		"""
		# Apply the &delta to the vertical position of the primary dimension changing
		# the set of visible elements.
		"""

		to = delta(self.visible[0])
		if to < 0:
			to = 0
		else:
			last = self.source.ln_count() - self.dimensions.lines
			if to > last:
				to = max(0, last)

		self.visibility[0].datum = to
		self.visible[0] = to

	def pan(self, delta):
		"""
		# Apply the &delta to the horizontal position of the secondary dimension changing
		# the visible units of the elements.
		"""

		to = delta(self.visible[1])
		if to < 0:
			to = 0

		self.visibility[1].datum = to
		self.visible[1] = to

	@staticmethod
	def backward(total, ln, offset):
		selections = [(ln, -1), (total-1, ln-1)]
		return (-1, selections, str.rfind, 0, offset)

	@staticmethod
	def forward(total, ln, offset):
		selections = [(ln, total), (0, ln)]
		return (1, selections, str.find, offset, None)

	def find(self, control, string):
		"""
		# Search for &string in &elements starting at the line offset &whence.
		"""

		v, h = self.focus

		termlength = len(string)
		d, selections, fmethod, start, stop = control
		srange = (start, stop)

		for area in selections:
			start, stop = area
			ilines = self.source.select(*area)

			for li in ilines:
				i = fmethod(li.ln_content, string, *srange)
				if i == -1:
					# Not in this line.
					srange = (0, None)
					continue
				else:
					v.set(li.ln_offset)
					self.vertical_changed(li.ln_offset)
					h.restore((i, i, i + termlength))
					return

	def seek(self, lo, unit):
		"""
		# Relocate the cursor to the &unit in &element.
		"""

		src = self.source
		li = src.sole(lo)
		width = self.dimensions.span

		self.focus[0].set(lo)
		self.focus[1].set(unit if unit is not None else li.ln_length)
		page_offset = lo - (width // 2)
		self.scroll(lambda x: page_offset)

	def delta(self, offset, change, *, max=max,
			ainsert=alignment.insert,
			adelete=alignment.delete,
		):
		"""
		# Adjust view positioning to compensate for changes in &elements and
		# propagate to parallels to maintain their views.

		# Executed on the target refraction after a change is performed.
		"""

		src = self.source
		total = src.ln_count()

		if change > 0:
			op = ainsert
			sign = +1
			total -= change
		else:
			op = adelete
			sign = -1
			total += (-change)

		for rf, v in getattr(self, 'parallels', ((self, None),)):
			assert rf.source is src
			position = rf.visible[0]
			visible = rf.dimensions.lines
			rf.visible[0] = op(total, visible, position, offset, sign*change)

		return self

	def vertical_changed(self, lo, *,
			backward=alignment.backward,
			forward=alignment.forward,
		):
		"""
		# Constrain the focus and apply margin scrolls.
		"""

		src = self.source
		total = src.ln_count()

		# Constrain vertical and identify indentation level (bol).
		ll = bol = 0
		if lo < 0 or not total:
			self.focus[0].set(0)
		elif lo >= total:
			self.focus[0].set(total - 1)
		else:
			line = src.sole(lo)
			ll = line.ln_length

		# Constrain cursor.
		h = self.focus[1]
		h.datum = max(bol, h.datum)
		h.magnitude = min(ll, h.magnitude)
		h.set(min(ll, max(bol, h.get())))
		assert h.get() >= 0 and h.get() <= ll

		# Margin scrolling.
		current = self.visible[0]
		rln = lo - current
		climit = max(0, self.limits[0])
		sunit = max(1, climit * 2)
		edge = self.dimensions.lines
		if rln <= climit:
			# Backwards
			position, rscroll, area = backward(total, edge, current, sunit)
			if lo < position:
				self.visible[0] = max(0, lo - (edge // 2))
			else:
				self.visible[0] = position
		else:
			if rln >= edge - climit:
				# Forwards
				position, rscroll, area = forward(total, edge, current, sunit)
				if not (position + edge) > lo:
					self.visible[0] = min(total - edge, lo - (edge // 2))
				else:
					self.visible[0] = position

	def field_areas(self, element):
		"""
		# Get the slices of the structured &element.
		"""

		areas = []
		offset = 0
		for typ, segment in element:
			s = slice(offset, offset + len(segment))
			areas.append(s)
			offset = s.stop

		return areas

	def fields(self, element:int):
		"""
		# Get the slices of the structured element.
		"""

		lff = self.forms.lf_fields
		ln = self.source.sole(element)
		fs = list(lff.isolate(lff.separation, ln))
		return self.field_areas(fs), fs

	def field_index(self, areas, offset):
		for i, s in enumerate(areas):
			if s.start > offset:
				# When equal, allow it continue so that
				# -1 can be applied unconditionally.
				break
		else:
			i = len(areas)
		i -= 1
		return i

	def field_select(self, quantity):
		hstart, h, hstop = self.focus[1].snapshot()
		if h >= hstart and h <= hstop:
			if quantity < 0:
				h = hstart
			elif quantity > 0:
				h = hstop - 1
		h = max(0, h)

		areas, ef = self.fields(self.focus[0].get())
		i = self.field_index(areas, h)

		if quantity < 0:
			end = -1
			step = -1
		else:
			end = len(areas)
			step = 1

		r = areas[i]
		assert r.stop > h and r.start <= h
		q = abs(quantity)
		for fi in range(i+step, end, step):
			f = ef[fi]
			if f[1].isspace():
				if f[0] in {'indentation', 'termination'}:
					# Restrict boundary.
					fi += -(step)
					break
				continue

			if f[0] in {'literal-delimit', 'literal-start', 'literal-stop'}:
				continue

			k = f[0].rsplit('-')[-1]
			if k in {'terminator', 'router', 'operation', 'separator', 'enclosure'}:
				# Don't count spaces or punctuation.
				continue

			q -= 1
			if q == 0:
				break
		else:
			fi = max(0, end - step)

		t = areas[fi]
		return fi, t

	def field(self, quantity):
		return self.field_select(quantity)[1]

	def unit(self, quantity):
		"""
		# Get the Character Units at the cursor position.
		"""

		lo = self.focus[0].get()
		cp = self.focus[1].get()
		return self.cu_codepoints(lo, cp, quantity)

	def vertical_selection_text(self) -> Iterable[types.Line]:
		"""
		# Lines of text in the vertical range.
		"""

		# Vertical Range
		start, position, stop = self.focus[0].snapshot()
		return self.source.select(start, stop)

	def horizontal_selection_text(self) -> str:
		"""
		# Text in the horizontal range of the cursor's line number.
		"""

		# Horizontal Range
		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		ln = self.source.sole(lo)
		return ln.ln_content[start:stop]

	def cwl(self) -> types.Line:
		"""
		# Get the current working line.
		"""

		return self.source.sole(self.focus[0].get())

	def phrase(self, offset):
		"""
		# Render the &types.Phrase instance for the given line.
		"""

		return next(self.forms.render((self.source.sole(offset),)))

	def iterphrases(self, start, stop):
		"""
		# Render the &types.Phrase instances for the given range.
		"""

		return self.forms.render(self.source.select(start, stop))

	def cu_codepoints(self, ln_offset, cp_offset, cu_offset) -> int:
		"""
		# Get the number of codepoints used to represent the
		# Character Unit identified by &ln_offset and &cp_offset.
		"""

		phrase = self.phrase(ln_offset)

		p, r = phrase.seek((0, 0), cp_offset, *phrase.m_codepoint)
		assert r == 0

		n, r = phrase.seek(p, cu_offset, *phrase.m_unit)
		assert r == 0

		return phrase.tell(phrase.areal(n), *phrase.m_codepoint)

	def take_vertical_range(self):
		"""
		# Delete and return the lines selected by the vertical range.
		"""

		start, position, stop = self.focus[0].snapshot()
		src = self.source

		lines = list(src.select(start, stop))
		src.delete_lines(start, stop)

		return (start, 0, lines)

	def take_horizontal_range(self):
		"""
		# Delete and return the span selected by the horizontal range.
		"""

		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		src = self.source

		selection = src.delete_codepoints(lo, start, stop)
		return (lo, start, [selection])

	def render(self, view, *lines):
		"""
		# Update the &view representations of &lines from &self.source.

		# [ Returns ]
		# Screen delta.
		"""

		start_of_view, left = self.visible
		src = self.source
		count = src.ln_count()
		rline = self.forms.render
		gline = self.source.sole

		for lo in lines:
			rlo = lo - start_of_view
			try:
				line = gline(lo)
			except IndexError:
				line = self.forms.ln_interpret("")
			ph = next(rline((line,)))
			area = slice(rlo, rlo+1)
			view.update(area, (ph,))
			yield from view.render(area)

	def update(self, view, changes, *,
			len=len, min=min, max=max, sum=sum, list=list,
			isinstance=isinstance, enumerate=enumerate,
		):
		"""
		# Identify and render the necessary changes to update the view
		# and the corresponding display. The view's image and offset are adjusted
		# as the rendering instructions are compiled; if it is recognized
		# that the view's image is largely discarded or overwritten, a frame
		# refresh will be emitted instead of the incremental changes.

		# [ Engineering ]
		# The process is rather complicated as accuracy requires the translation
		# of line offsets in the past to where they are in the future. The
		# position of the view is also subject to this which means that much
		# filtering can only be performed after its final position is identified.

		# While difficult to measure, it is important that minimal effort is exerted here.
		# When large or complex changes are processed, it may be more efficient
		# to render a new image.
		"""

		src = self.source
		va = view.area
		dvh = self.visibility[1].datum
		if view.horizontal_offset != dvh:
			# Full refresh for horizontal scrolls. Panning being
			# irregular, leave suboptimal for the moment.
			view.pan_relative(slice(0, None), dvh - view.horizontal_offset)
			view.horizontal_offset = dvh
			yield from self.refresh(view, self.visible[0])
			return

		# Future state; view.offset is current.
		visible = va.lines
		start_of_view = self.visible[0]
		end_of_view = start_of_view + visible
		total = src.ln_count()

		# Reconstruct total so that view changes can be tracked as they were.
		dr = list(changes)
		dt = sum(r.change for r in dr)
		vt = total - dt

		updates = [] # Lines to update after view realignment.
		dimage = [] # Display (move) instructions to adjust for the delta.
		image_size = len(view.image)

		for r in dr:
			index = r.element or 0
			if isinstance(r, delta.Update):
				# Note updates for translating.
				updates.append(index)
				continue

			if image_size < 4:
				# When lines are inserted or removed,
				# Refresh when the remaining image is small.
				yield from self.refresh(view, start_of_view)
				return

			vo = view.offset
			whence = index - vo
			ve = vo + visible

			if ve >= vt and vo > 0:
				# When on last page and first is not last.
				dins = alignment.stop_relative_insert
				ddel = alignment.stop_relative_delete
				last_page = True
			else:
				dins = alignment.start_relative_insert
				ddel = alignment.start_relative_delete
				last_page = False

			nd = len(r.deletion or ())
			ni = len(r.insertion or ())
			di = ni - nd
			# Identify the available lines before applying the change to &vt.
			limit = min(visible, vt)
			vt += di

			if di == 0:
				# No change in elements length.
				assert nd == ni
				updates.extend(range(index, index + ni))
				continue
			else:
				# Translate the indexes of past updates.
				# Transmit updates last in case the view's offset changes.
				for i, v in enumerate(updates):
					if index <= v:
						updates[i] += di

			if not isinstance(r, delta.Lines) or (index >= ve and not last_page):
				# Filter non-lines or out of scope changes.
				continue

			if nd:
				# Deletion

				if whence < 0:
					# Adjust view offset and identify view local deletion.
					d = max(0, whence + nd)
					w = 0
					if not last_page:
						view.offset -= (nd - d)
				else:
					assert whence >= 0
					w = whence
					d = min(nd, visible - whence)

				if last_page:
					view.offset -= nd
					# Apply prior to contraining &d to the available area.
					# In negative &whence cases, &view.offset has already
					# been adjusted for the changes before the view.
					if view.offset <= 0:
						# Delete caused transition.
						view.offset = 0
						s = view.delete(w, d)
						s = view.prefix(list(self.iterphrases(0, d)))
						dimage.append(view.render(s))
						image_size -= d
						continue

				if d:
					# View local changes.
					s = view.delete(w, d)
					image_size -= d
					dimage.append((ddel(view.area, s.start, s.stop),))
			elif ni:
				# Insertion

				if last_page:
					view.offset += ni
					d = min(visible, ni)
				elif whence < 0:
					# Nothing but offset updates.
					view.offset += ni
					continue
				else:
					d = max(0, min(visible - whence, ni))

				s = view.insert(whence, d)
				dimage.append((dins(va, s.start, s.stop),))
				updates.extend(range(index, index+d))

				image_size -= d
			else:
				assert False # Never; continued at `di == 0`.
		else:
			# Initialize last_page for zero change cases.
			# Usually, scroll operations.
			ve = view.offset + visible
			if ve >= total and view.offset > 0:
				last_page = True
			else:
				last_page = False

		# After the deltas have been translated and enqueued

		dv = start_of_view - view.offset
		if abs(dv) >= visible or image_size < 4:
			# Refresh when scrolling everything out.
			yield from self.refresh(view, start_of_view)
			return

		if dv:
			# Scroll view.
			if dv > 0:
				# View's position is before the refraction's.
				# Advance offset after aligning the image.
				view.delete(0, dv)
				view.offset += dv
				dimage.append([alignment.scroll_backward(view.area, dv)])
			else:
				# View's position is beyond the refraction's.
				# Align the image with prefix.
				s = view.prefix(list(self.iterphrases(start_of_view, start_of_view-dv)))
				view.trim()
				dimage.append([alignment.scroll_forward(view.area, -dv)] + list(view.render(s)))

		# Trim or Compensate
		displayed = len(view.image)
		available = min(visible, total)
		if displayed > visible:
			# Trim.
			view.trim()
			dimage.append(view.compensate())
		elif displayed < available:
			if last_page:
				stop = start_of_view + (available - displayed)
				s = view.prefix(list(self.iterphrases(start_of_view, stop)))
				view.offset += s.stop - s.start
				dimage.append(view.render(s))
			else:
				tail = start_of_view + displayed
				stop = start_of_view + available
				s = view.suffix(list(self.iterphrases(tail, stop)))
				dimage.append(view.render(s))

			# Pad with Empty if necessary.
			yield from view.compensate()

		# Transmit delta.
		for x in dimage:
			yield from x

		# Update line in view.
		for lo in updates:
			# Translated line indexes. (past to present)
			if lo >= start_of_view and lo < end_of_view:
				yield from self.render(view, lo)

	def refresh(self, view:View, whence:int):
		"""
		# Overwrite &view.image with the elements in &rf
		# starting at the absolute offset &whence.

		# The &view.offset is updated to &whence, but &self.visibility is presumed
		# to be current.
		"""

		visible = view.area.lines
		phrases = list(self.iterphrases(whence, whence+visible))
		pad = visible - len(phrases)
		if pad > 0:
			phrases.extend([view.Empty] * pad)
		view.update(slice(0, visible), phrases)
		view.trim()
		view.offset = whence

		return view.render(slice(0, visible))

class Frame(Core):
	"""
	# Frame implementation for laying out and interacting with a set of refactions.

	# [ Elements ]
	# /area/
		# The location and size of the frame on the screen.
	# /index/
		# The position of the frame in the session's frame set.
	# /title/
		# User assigned identifier for a frame.
	# /deltas/
		# Enqueued display deltas.
	"""

	area: Area
	title: str
	structure: object
	vertical: int
	division: int
	focus: Refraction
	view: View

	refractions: Sequence[Refraction]
	returns: Sequence[Refraction|None]

	def __init__(self, define, theme, fs, keyboard, area, index=None, title=None):
		self.define = define
		self.theme = theme
		self.border = theme['frame-border']
		self.filesystem = fs
		self.keyboard = keyboard
		self.area = area
		self.index = index
		self.title = title
		self.structure = Model()

		self.vertical = 0
		self.division = 0
		self.focus = None
		self.view = None

		self.paths = {} # (vertical, division) -> element-index
		self.headings = []
		self.panes = []
		self.views = []
		self.refractions = []
		self.returns = []
		self.parallels = {}
		self.deltas = []

	def refracting(self, ref:Reference, *sole) -> Iterable[Refraction]:
		"""
		# Iterate through all the Refractions viewing &ref and
		# its associated view. &sole, as an iterable, is returned if
		# no refractions are associated with &ref.
		"""

		return self.parallels.get(ref.ref_path, sole)

	def attach(self, dpath, rf) -> types.View:
		"""
		# Assign the &rf to the view associated with
		# the &division of the &vertical.

		# [ Returns ]
		# A view instance whose refresh method should be dispatched
		# to the display in order to update the screen.
		"""

		src = rf.source
		vi = self.paths[dpath]
		current = self.refractions[vi]
		self.returns[vi] = current
		view = self.views[vi]
		self.parallels[current.source.origin.ref_path].discard((current, view))

		self.refractions[vi] = rf
		mirrors = self.parallels[src.origin.ref_path]
		mirrors.add((rf, view))
		rf.parallels = weakref.proxy(mirrors)

		if (self.vertical, self.division) == dpath:
			self.refocus()

		# Configure and refresh.
		rf.configure(view.area)
		view.offset = rf.visible[0]
		view.horizontal_offset = rf.visible[1]
		view.version = src.version()
		vslice = view.vertical(rf)
		view.update(slice(0, None), list(rf.iterphrases(vslice.start, vslice.stop)))

		return view

	def chpath(self, dpath, reference, *, snapshot=(0, 0, None)):
		"""
		# Update the refraction's location.
		"""

		header = self.headings[self.paths[dpath]]
		header.truncate()
		header.offset = 0
		header.version = snapshot

		from dataclasses import replace
		fctx = self.filesystem.lf_fields
		fctx = replace(fctx, separation=(lambda: reference.ref_context))
		fs_lf = replace(self.filesystem, lf_fields=fctx)

		lines = location.determine(reference.ref_context, reference.ref_path)
		lines = map(fs_lf.ln_interpret, lines)
		header.update(slice(0, 2), list(fs_lf.render(lines)))
		return header.render(slice(0, 2))

	def chresource(self, path, refraction):
		"""
		# Change the resource associated with the &division and &vertical
		# to the one identified by &path.
		"""

		yield from self.attach(path, refraction).refresh()
		yield from self.chpath(path, refraction.source.origin)

	def fill(self, refractions):
		"""
		# Fill the views with the given &refractions overwriting any.
		"""

		self.refractions[:] = refractions
		self.parallels.clear()

		# Align returns size.
		n = len(self.refractions)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for ((v, d), rf, view) in zip(self.panes, self.refractions, self.views):
			view.Empty = types.text.Phrase([
				types.text.Words((0, "", rf.forms.lf_theme['empty']))
			])
			rf.configure(view.area)
			self.parallels[rf.source.origin.ref_path].add((rf, view))

	def remodel(self, area=None, divisions=None):
		"""
		# Update the model in response to changes in the size or layout of the frame.
		"""

		# Default to existing configuration.
		da, dd = self.structure.configuration
		if area is None:
			area = da
		if divisions is None:
			divisions = dd

		self.structure.configure(area, divisions)

		self.parallels = collections.defaultdict(set)
		self.panes = list(self.structure.iterpanes())
		self.paths = {p: i for i, p in enumerate(self.panes)}

		self.views = list(
			View(Area(*ctx), [], [], {'top': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area)
		)

		# Resource Locations
		self.headings = list(
			View(Area(*ctx), [], [], {'bottom': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area, section=1)
		)

		# Command Prompts, zero heights by default.
		self.footers = list(
			View(Area(*ctx), [], [], {'top': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area, section=3)
		)

	def refresh(self):
		"""
		# Refresh the view images.
		"""

		for rf, view in zip(self.refractions, self.views):
			rf.refresh(view, rf.visible[0])
			view.version = rf.source.version()

	def resize(self, area):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		rfcopy = list(self.refractions)
		self.area = area
		self.remodel(area)

		self.fill(rfcopy)
		self.refocus()
		self.refresh()

	def returnview(self, dpath):
		"""
		# Switch the Refraction selected at &dpath with the one stored in &returns.
		"""

		previous = self.returns[self.paths[dpath]]
		if previous is not None:
			yield from self.attach(dpath, previous).refresh()
			yield from self.chpath(dpath, previous.source.origin)

	def render(self, screen):
		"""
		# Render a complete frame using the current view image state.
		"""

		for p, rf, v, f in zip(self.panes, self.refractions, self.views, self.footers):
			yield from self.chpath(p, rf.source.origin)
			yield from v.render(slice(0, v.height))
			yield from f.render(slice(0, f.height))

		aw = self.area.span
		ah = self.area.lines

		# Give the frame boundaries higher (display) precedence by rendering last.
		yield from self.fill_areas(self.structure.r_enclose(aw, ah))
		yield from self.fill_areas(self.structure.r_divide(aw, ah))

	def select(self, dpath):
		"""
		# Get the &Refraction and &View pair at the given
		# vertical-divsion &dpath.
		"""

		i = self.paths[dpath]
		return (self.refractions[i], self.views[i])

	def refocus(self):
		"""
		# Adjust for a focus change in the root refraction.
		"""

		path = (self.vertical, self.division)
		if path not in self.paths:
			if path[1] < 0:
				v = path[0] - 1
				if v < 0:
					v += self.structure.verticals()
				path = (v, self.structure.divisions(v)-1)
			else:
				path = (path[0]+1, 0)
				if path not in self.paths:
					path = (0, 0)

			self.vertical, self.division = path

		self.focus, self.view = self.select(path)

	def resize_footer(self, dpath, height):
		"""
		# Adjust the size, &height, of the footer for the given &dpath.
		"""

		rf, v = self.select(dpath)
		f = self.footers[self.paths[dpath]]

		d = self.structure.set_margin_size(dpath[0], dpath[1], 3, height)
		f.area = f.area.resize(d, 0)

		# Initial opening needs to include the border size.
		if height - d == 0:
			# height was zero. Pad with border width.
			d += self.structure.fm_border_width
		elif height == 0 and d != 0:
			# height set to zero. Compensate for border.
			d -= self.structure.fm_border_width

		v.area = v.area.resize(-d, 0)
		rf.configure(v.area)

		f.area = f.area.move(-d, 0)
		# &render will emit the entire image, so make sure the footer is trimmed.
		f.trim()
		f.compensate()
		return d

	def fill_areas(self, patterns, *, Area=Area, ord=ord):
		"""
		# Generate the display instructions for rendering the given &patterns.

		# [ Parameters ]
		# /patterns/
			# Iterator producing area and fill character pairs.
		"""

		Type = self.border
		for avalues, fill_char in patterns:
			a = Area(*avalues)
			yield a, [Type.inscribe(ord(fill_char))] * a.volume

	def prepare(self, session, type, dpath, *, extension=None):
		"""
		# Shift the focus to the prompt of the focused refraction.
		# If no prompt is open, initialize it.
		"""

		from .query import refract, issue
		vi = self.paths[dpath]
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		view = self.footers[vi]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		# Make footer visible if the view is empty.
		if view.height == 0:
			self.resize_footer(dpath, 1)
			session.dispatch_delta(
				self.fill_areas(
					self.structure.r_patch_footer(dpath[0], dpath[1])
				)
			)

		self.focus, self.view = (
			refract(session, self, view, context, state, issue),
			view,
		)

	def relocate(self, session, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# load the data into a session resource for editing in the view.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].source.origin
		lf = session.load_type('filesystem')

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(lf, view, ref.ref_context, ref.ref_path, location.open),
			view,
		)

		self.focus.annotation = annotations.Filesystem('open',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	def rewrite(self, session, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# write the subject's elements to the location upon activation.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].source.origin
		lf = session.load_type('filesystem')

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(lf, view, ref.ref_context, ref.ref_path, location.save),
			view,
		)

		self.focus.annotation = annotations.Filesystem('save',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	def cancel(self):
		"""
		# Refocus the subject refraction and discard any state changes
		# performed to the location heading.
		"""

		rf = self.focus
		view = self.view
		dpath = (self.vertical, self.division)

		if self.footers[self.paths[dpath]] is view:
			# Overwrite the prompt.
			d = self.close_prompt(dpath)
			assert d < 0
			vo = self.view.offset
			vh = self.view.height
			end = vo + vh
			start = end + d
			vrange = slice(vh + d, vh)
			self.view.update(vrange, list(rf.iterphrases(start, end)))
			yield from self.view.render(vrange)
			yield from self.view.compensate()
			return

		self.refocus()
		if rf is self.focus:
			# Not a location or command; check annotation.
			if rf.annotation is not None:
				rf.annotation.close()
				rf.annotation = None
			return

		# Restore location.
		src = rf.source
		rf.visibility[0].datum = view.offset
		rf.visibility[1].datum = view.horizontal_offset
		rf.visible[:] = (view.offset, view.horizontal_offset)
		yield from self.chpath(dpath, self.focus.source.origin, snapshot=src.version())

	def close_prompt(self, dpath):
		"""
		# Set the footer size of the division identified by &dpath to zero
		# and refocus the division if the prompt was focused by the frame.
		"""

		d = 0
		index = self.paths[dpath]
		f = self.footers[index]

		rf = self.focus
		fv = self.view

		if f.height > 0:
			d = self.resize_footer(dpath, 0)

		# Prompt was focused.
		if fv is f:
			self.refocus()

		return d

	def target(self, top, left):
		"""
		# Identify the target refraction from the given cell coordinates.

		# [ Returns ]
		# # Triple identifying the vertical, division, and section.
		# # &Refraction
		# # &View
		"""

		v, d, s = self.structure.address(left, top)
		i = self.paths[(v, d)]
		return ((v, d, s), self.refractions[i], self.views[i])

	@staticmethod
	def cursor_cell(positions):
		"""
		# Apply changes to the cursor positions for visual indicators.
		"""

		if positions[1] >= positions[2]:
			# after last character in range
			return 'cursor-stop-exclusive'
		elif positions[1] < positions[0]:
			# before first character in range
			return 'cursor-start-exclusive'
		elif positions[0] == positions[1]:
			# on first character in range
			return 'cursor-start-inclusive'
		elif positions[2]-1 == positions[1]:
			# on last character in range
			return 'cursor-stop-inclusive'
		else:
			# between first and last characters
			return 'cursor-offset-active'

	def indicate(self, focus, view):
		"""
		# Render the (cursor) status indicators.

		# [ Parameters ]
		# /focus/
			# The &Refraction whose position indicators are being drawn.
		# /view/
			# The &.types.View connected to the refraction.

		# [ Returns ]
		# Iterable of screen deltas.
		"""

		src = focus.source
		fai = focus.annotation
		lf = focus.forms
		rx, ry = (0, 0)
		ctx = view.area
		vx, vy = (ctx.left_offset, ctx.top_offset)
		hoffset = view.horizontal_offset
		top, left = focus.visible
		hedge, edge = (ctx.span, ctx.lines)
		empty_cell = focus.forms.lf_theme['empty'].inscribe(ord(' '))

		# Get the cursor line.
		v, h = focus.focus
		ln = v.get()
		rln = ln - top

		try:
			li = src.sole(ln)
		except IndexError:
			li = types.Line(ln, 0, "")

		h.limit(0, len(li.ln_content))

		# Prepare phrase and cells.
		lfields = lf.lf_fields.partial()(li)
		if fai is not None:
			fai.update(li.ln_content, lfields)
			caf = lf.compose(types.Line(ln, 0, ""), annotations.delimit(fai))
			phrase = lf.compose(li, lfields)
			phrase = types.Phrase(itertools.chain(lf.compose(li, lfields), caf))
		else:
			phrase = types.Phrase(lf.compose(li, lfields))

		# Translate codepoint offsets to cell offsets.
		m_cell = phrase.m_cell
		m_cp = phrase.m_codepoint
		m_cu = phrase.m_unit

		hs = tuple(x + li.ln_level for x in h.snapshot())
		if hs[0] > hs[2]:
			inverted = True
			hs = tuple(reversed(hs))
		else:
			inverted = False

		# Seek the codepoint and align on the next word with real text.
		cursor_p = phrase.areal(phrase.seek((0, 0), hs[1], *m_cp)[0])

		cursor_start = phrase.tell(cursor_p, *m_cell)
		cursor_word = phrase[cursor_p[0]]
		cursor_stop = cursor_start + min(cursor_word.cellcount(), cursor_word.cellrate)

		rstart = phrase.tell(phrase.seek((0, 0), hs[0], *m_cp)[0], *m_cell)
		rstop = phrase.tell(phrase.seek((0, 0), hs[2], *m_cp)[0], *m_cell)
		hc = [rstart, cursor_start, rstop]

		# Ignore when offscreen.
		if rln >= 0 and rln < edge:
			kb_mode = self.keyboard.mapping
			cells = list(phrase.render(Define=self.define))

			if cursor_start >= len(cells) - 1:
				# End of line position.
				ccell = self.theme['cursor-void']
			else:
				ccell = self.theme[self.cursor_cell(hs)]

			if kb_mode == 'insert':
				cells[cursor_start:cursor_stop] = [
					c.update(underline=types.LineStyle.solid, linecolor=ccell.cellcolor)
					for c in cells[cursor_start:cursor_stop]
				]
			else:
				cells[cursor_start:cursor_stop] = [
					c.update(textcolor=c.cellcolor, cellcolor=ccell.cellcolor)
					for c in cells[cursor_start:cursor_stop]
				]

				# Range underline; disabled when inserting.
				cells[rstart:rstop] = [
					c.update(underline=types.LineStyle.solid, linecolor=0x66cacaFF)
					for c in cells[rstart:rstop]
				]

			yield ctx.__class__(vy + rln, vx, 1, hedge), cells[hoffset:hoffset+hedge]

		si = list(self.structure.scale_ipositions(
			self.structure.indicate,
			(vx - rx, vy - ry),
			(hedge, edge),
			hc,
			v.snapshot(),
			left, top,
		))

		for pi in self.structure.r_indicators(si, rtypes=view.edges):
			(x, y), itype, ic, bc = pi
			ccell = self.theme['cursor-' + itype]
			picell = Glyph(textcolor=ccell.cellcolor, codepoint=ord(ic))
			yield ctx.__class__(y, x, 1, 1), (picell,)

class Session(Core):
	"""
	# Root application state.

	# [ Elements ]
	# /configuration/
		# The loaded set of application defaults.
	# /host/
		# The system execution context of the host machine.
	# /logfile/
		# Transcript override for logging.
	# /io/
		# System I/O abstraction for command substitution and file I/O.
	# /device/
		# The target display and event source.
	# /types/
		# Mapping of syntax types default reformulation instances.
		# Used when importing resources.
	# /resources/
		# Mapping of file paths to &Resource instances.
	# /systems/
		# System contexts currently available for use within the session.
	# /placement/
		# Invocation defined position and dimensions as a tuple pair.
		# Defined by &__init__.Parameters.position and &__init__.Parameters.dimensions.
	"""

	host: types.System
	executable: files.Path
	resources: Mapping[files.Path, Resource]
	systems: Mapping[System, Execution]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]

	@staticmethod
	def integrate_theme(colors):
		cell = Glyph(codepoint=-1,
			cellcolor=colors.palette[colors.cell['default']],
			textcolor=colors.palette[colors.text['default']],
		)

		theme = {
			k : cell.update(textcolor=colors.palette[v])
			for k, v in colors.text.items()
		}

		for k, v in colors.cell.items():
			theme[k] = theme.get(k, cell).update(cellcolor=colors.palette[v])

		theme['title'] = theme['field-annotation-title']
		theme['empty'] = cell.inscribe(-1)

		return theme

	@staticmethod
	def integrate_controls(controls):
		defaults = {
			'control': controls.control,
			'insert': controls.insert,
			'annotations': controls.annotations,
			'capture-key': ia.types.Mode(('delta', ('insert', 'capture', 'key'), ())),
			'capture-insert': ia.types.Mode(('delta', ('insert', 'capture'), ())),
			'capture-replace': ia.types.Mode(('delta', ('replace', 'capture'), ())),
		}

		ctl = ia.types.Selection(defaults)
		ctl.set('control')

		# Translations for `distributed` qualification.
		# Maps certain operations to vertical or horizontal mapped operations.
		ctl.redirections['distributed'] = {
			('delta', x): ('delta', y)
			for x, y in [
				(('character', 'swap', 'case'), ('horizontal', 'swap', 'case')),
				(('delete', 'unit', 'current'), ('delete', 'horizontal', 'range')),
				(('delete', 'unit', 'former'), ('delete', 'vertical', 'column')),
				(('delete', 'element', 'current'), ('delete', 'vertical', 'range')),
				(('delete', 'element', 'former'), ('delete', 'vertical', 'range')),

				(('indentation', 'increment'), ('indentation', 'increment', 'range')),
				(('indentation', 'decrement'), ('indentation', 'decrement', 'range')),
				(('indentation', 'zero'), ('indentation', 'zero', 'range')),
			]
		}

		return ctl

	@staticmethod
	def integrate_types(cfgtypes, theme):
		ce, ltc, lic, isize = cfgtypes.formats[cfgtypes.Default]

		from fault.system.text import cells as syscellcount
		from ..cells.text import graphemes, words
		cus = tools.cachedcalls(256)(
			tools.compose(list, words,
				tools.partial(graphemes, syscellcount, ctlsize=4, tabsize=4)
			)
		)

		from fault.syntax import format

		return types.Reformulations(
			"", theme,
			format.Characters.from_codec(ce, 'surrogateescape'),
			format.Lines(ltc, lic),
			None,
			cus,
		)

	@staticmethod
	def integrate_events(ia):
		return {
			x.i_category: x.select
			for x in ia.sections()
		}

	def __init__(self, cfg, system, io, executable, terminal:Device, position=(0,0), dimensions=None):
		self.focus = None
		self.frame = 0
		self.frames = []

		self.configuration = cfg
		self.events = self.integrate_events(ia)
		self.theme = self.integrate_theme(cfg.colors)
		self.keyboard = self.integrate_controls(cfg.controls)
		self.host = system
		self.logfile = None
		self.io = io
		self.placement = (position, dimensions)

		self.executable = executable.delimit()
		self.device = terminal
		self.cache = [] # Lines

		ltype = self.integrate_types(self.configuration.types, self.theme)
		self.types = {
			"": ltype, # Root type.
			'filesystem': ltype.replace(lf_fields=fields.filesystem_paths),
		}
		self.types['lambda'] = self.load_type('lambda') # Default syntax type.

		exepath = self.executable/'transcript'
		editor_log = Reference(
			self.host.identity, 'filepath',
			str(exepath), self.executable,
			exepath
		)
		self.transcript = Resource(editor_log, self.load_type('lambda'))
		self.resources = {
			self.executable/'transcript': self.transcript
		}

		self.process = Execution(
			types.System(
				'process',
				system.identity.sys_credentials,
				'',
				system.identity.sys_identity,
			),
			'utf-8',
			None,
			[],
		)

		self.systems = {
			self.host.identity: self.host,
			self.process.identity: self.process,
		}

	def load(self):
		from .session import structure_frames as parse
		with open(self.fs_snapshot) as f:
			fspecs = parse(f.read())
		if self.frames:
			self.frames = []
		self.restore(fspecs)

	def store(self):
		from .session import sequence_frames as seq
		with open(self.fs_snapshot, 'w') as f:
			f.write(seq(self.snapshot()))

	def configure_logfile(self, logfile):
		"""
		# Assign the session's logfile and set &log to &write_log_file.
		"""

		self.logfile = logfile
		self.log = self.write_log_file

	def configure_transcript(self):
		"""
		# Set &log to &extend_transcript for in memory logging.
		"""

		self.log = self.extend_transcript

	def allocate_resource(self, ref:Reference) -> Resource:
		"""
		# Create a &Resource instance using the given reference as it's origin.
		"""

		return Resource(ref, self.load_type(ref.ref_type))

	def import_resource(self, ref:Reference) -> Resource:
		"""
		# Return a &Resource associated with the contents of &path and
		# add it to the resource set managed by &self.
		"""

		if ref.ref_path in self.resources:
			return self.resources[ref.ref_path]

		rs = self.allocate_resource(ref)
		self.load_resource(rs)
		self.resources[ref.ref_path] = rs

		return rs

	@staticmethod
	def buffer_data(size, file):
		buf = file.read(size)
		while len(buf) >= size:
			yield buf
			buf = file.read(size)
		yield buf

	def load_resource(self, src:Resource):
		"""
		# Load and retain the lines of the resource identified by &src.origin.
		"""

		path = src.origin.ref_path
		lf = src.forms
		codec = lf.lf_codec
		lines = lf.lf_lines

		try:
			with path.fs_open('rb') as f:
				src.status = path.fs_status()
				ilines = lines.structure(codec.structure(self.buffer_data(1024, f)))
				cpr = map(lf.ln_sequence, (types.Line(-1, il, lc) for il, lc in ilines))
				src.elements = sequence.Segments(cpr)
		except FileNotFoundError:
			self.log("Resource does not exist: " + str(path))
		except Exception as load_error:
			self.error("Exception during load. Continuing with empty document.", load_error)
		else:
			# Initialized.
			return

		self.log("Writing will attempt to create the file and any leading paths.")

	@staticmethod
	def buffer_lines(ilines):
		# iter(elements) is critical here; repeating the running iterator
		# as islice continues to take processing units to be buffered.
		ielements = itertools.repeat(iter(ilines))
		ilinesets = (itertools.islice(i, 512) for i in ielements)

		buf = bytearray()
		for lines in ilinesets:
			bl = len(buf)
			for line in lines:
				buf += line

			if bl == len(buf):
				yield buf
				break
			elif len(buf) > 0xffff:
				yield buf
				buf = bytearray()

	def store_resource(self, src:Resource):
		"""
		# Write the elements of the process local resource, &src, to the file
		# identified by &src.origin using the origin's system context.
		"""

		ref = src.origin
		codec = src.forms.lf_codec
		lform = src.forms.lf_lines
		exectx = self.systems[ref.ref_system]
		self.log(f"Writing {len(src.elements)} [{str(src.forms)}] lines to [{ref}]")

		path = ref.ref_path
		if path.fs_type() == 'void':
			leading = (path ** 1)
			if leading.fs_type() == 'void':
				self.log(f"Allocating directories: " + str(leading))
				path.fs_alloc() # Leading path not present on save.

		ilines = lform.sequence((li.ln_level, li.ln_content) for li in src.select(0, src.ln_count()))
		ibytes = codec.sequence(ilines)
		idata = self.buffer_lines(ibytes)
		size = 0

		with open(ref.ref_identity, 'wb') as file:
			for data in idata:
				size += len(data)
				file.write(data)

		st = path.fs_status()
		self.log(f"Finished writing {size!r} bytes.")

		if st.size != size:
			self.log(f"Calculated write size differs from system reported size: {st.size}")

		if src.status is None:
			self.log("No previous modification time, file is new.")
		else:
			age = src.age(st.last_modified)
			if age is not None:
				self.log("Last modification was " + age + " ago.")

		src.saved = src.modifications.snapshot()
		src.status = st

	def delete_resource(self, rs:Resource):
		"""
		# Remove the process local resource, &rs, from the session's list.
		"""

		del self.resources[rs.origin.ref_path]

	def lookup_type(self, path:files.Path):
		cfgtypes = self.configuration.types
		return cfgtypes.filename_extensions.get(path.extension, 'lambda')

	def default_type(self):
		return self.types['']

	def load_type(self, sti):
		"""
		# Load and cache the syntax profile identified by &path.
		"""

		# Cached types.Reformulations instance.
		if sti in self.types:
			return self.types[sti]

		syntax_record = self.configuration.load_syntax(sti)
		fimethod, ficonfig, ce, eol, ic, ils = syntax_record

		from fault.syntax import format

		lf = self.default_type().replace(
			lf_type=sti,
			lf_lines=format.Lines(eol, ic),
			lf_codec=format.Characters.from_codec(ce, 'surrogateescape'),
			lf_fields=fields.prepare(fimethod, ficonfig),
		)

		self.types[sti] = lf
		return lf

	def reference(self, path):
		"""
		# Construct a &Reference instance from &path resolving types according to
		# the session's configuration.
		"""

		return Reference(
			self.host.identity,
			self.lookup_type(path),
			str(path),
			path.context or path ** 1,
			path,
		)

	def refract(self, path):
		"""
		# Construct a &Refraction for the resource identified by &path.
		# A &Resource instance is created if the path has not been loaded.
		"""

		return Refraction(self.import_resource(self.reference(path)))

	def log(self, *lines):
		"""
		# Append the given &lines to the transcript.
		# Overridden by (system/environ)`TERMINAL_LOG`.
		"""

		return self.extend_transcript(lines)

	def write_log_file(self, *lines):
		"""
		# Append the given &lines to the transcript.
		"""

		self.logfile.write('\n'.join(lines)+'\n')

	def extend_transcript(self, lines):
		"""
		# Open the virtual transcript resource and extend its elements with
		# the given &lines.

		# The default &log receiver.
		"""

		rsrc = self.transcript
		log = rsrc.modifications
		rsrc.extend_lines(lines)
		rsrc.commit()

		# Initialization cases where a frame is not available.
		frame = self.focus
		if frame is None:
			return

		for trf, v in frame.refracting(rsrc.origin):
			if trf == frame.focus:
				# Update handled by main loop.
				continue

			trf.seek(rsrc.ln_count(), 0)
			changes = rsrc.changes(v.version)
			tupdate = trf.update(v, changes)
			#tupdate = trf.refresh(v, 0)
			v.version = trf.source.version()
			self.dispatch_delta(tupdate)

	def resize(self):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		self.device.reconnect()
		new = self.device.screen.area
		for frame in self.frames:
			frame.resize(new)
		self.dispatch_delta(self.focus.render(self.device.screen))

	def refocus(self):
		"""
		# Change the focus to reflect the selection designated by &frame.

		# In cases of overflow, wrap the frame index.
		"""

		nframes = len(self.frames)
		if self.frame < 0:
			self.frame = nframes + (self.frame % -nframes)

		try:
			self.focus = self.frames[self.frame]
		except IndexError:
			if nframes == 0:
				# Exit condition.
				self.focus = None
				self.frame = None
				return
			else:
				self.frame = self.frame % nframes
				self.focus = self.frames[self.frame]

		self.focus.refocus()

	def reframe(self, index):
		"""
		# Change the selected frame and redraw the screen to reflect the new status.
		"""

		screen = self.device.screen
		last = self.frame
		self.frame = index
		self.refocus()
		self.dispatch_delta(self.focus.render(self.device.screen))

		# Use &self.frame as refocus may have compensated.
		self.device.update_frame_status(self.frame, last)

	def allocate(self, layout=None, area=None, title=None):
		"""
		# Allocate a new frame.

		# [ Returns ]
		# The index of the new frame.
		"""

		screen = self.device.screen

		if area is None and layout is None:
			if self.focus is not None:
				area = self.focus.structure.configuration[0]
				layout = self.focus.structure.fm_layout
			else:
				area = screen.area
		else:
			if area is None:
				area = screen.area

		if layout is None:
			layout = []
			v = area.span // 100
			available = max(0, v-1)
			for i in range(available):
				layout.append((1, i))
			layout.append((2, layout[-1][1] + 1))
		divcount = sum(x[0] for x in layout)

		f = Frame(
			self.device.define, self.theme,
			self.load_type('filesystem'),
			self.keyboard, area,
			index=len(self.frames),
			title=title
		)
		self.frames.append(f)

		f.remodel(area, layout)
		f.fill(map(self.refract, [files.root@'/dev/null' for x in range(divcount)]))
		f.refresh()
		self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])
		return f.index

	def resequence(self):
		"""
		# Update the indexes of the frames to reflect their positions in &frames.
		"""

		for i, f in enumerate(self.frames):
			f.index = i

	def release(self, frame):
		"""
		# Destroy the &frame in the session.
		"""

		del self.frames[frame]
		self.resequence()

		if not self.frames:
			# Exit condition.
			self.frame = None
			self.device.update_frame_list()
			return
		else:
			self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])
			if frame == self.frame:
				# Switch to a different frame.
				self.reframe(frame)
			else:
				# Off screen frame.
				pass

	@staticmethod
	def limit_resources(limit, rlist, null=files.root@'/dev/null'):
		"""
		# Truncate and compensate the given &rlist by &limit using &null.
		"""

		del rlist[limit:]
		n = len(rlist)
		if n < limit:
			rlist.extend(null for x in range(limit - n))

	def restore(self, frames):
		"""
		# Allocate and fill the &frames in order to restore a session.
		"""

		for frame_id, divcount, layout, resources, returns in frames:
			# Align the resources and returns with the layout.
			self.limit_resources(divcount, resources)
			self.limit_resources(divcount, returns)

			# Allocate a new frame and attach refractions.
			fi = self.allocate(layout, title=frame_id or None)
			f = self.frames[fi]
			f.fill(map(self.refract, resources))
			f.returns[:divcount] = map(self.refract, returns)

			# Populate View images.
			f.refresh()

		if 0:
			self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])

	def snapshot(self):
		"""
		# Construct a snapshot of the session suitable for sequencing with
		# &.session.sequence_frames.
		"""

		for f in self.frames:
			frame_id = f.title
			resources = [rf.source.origin.ref_path for rf in f.refractions]
			returns = [rf.source.origin.ref_path for rf in f.returns if rf is not None]

			yield (frame_id, f.structure.layout, resources, returns)

	def chresource(self, frame, path):
		self.dispatch_delta(frame.chresource((frame.vertical, frame.division), self.refract(path)))

	def error(self, context, exception):
		"""
		# Log the &exception.
		"""
		import traceback

		self.log(
			"-" * 80,
			context,
			"." * 80,
			*itertools.chain.from_iterable(
				line.rstrip('\n\r').split('\n') for line in (
					traceback.format_exception(exception)
				)
			)
		)

	def dispatch_delta(self, ixn):
		d = self.device
		s = d.screen
		for area, data in ixn:
			if data.__class__ is area.__class__:
				# Copy the cell pixels in the frame buffer.
				# Explicitly synchronizing here is necessary to flush
				# the screen state so that the replicate instruction may
				# work with the desired frame.
				d.replicate_cells(area, data)
				d.synchronize()

				# No invalidation necessary here as the cell replication
				# has been performed directly on the frame buffer.
				s.replicate(area, data.y_offset, data.x_offset)
			else:
				# Update the screen with the given data and signal
				# the display to refresh the area.
				s.rewrite(area, data)
				d.invalidate_cells(area)

	intercepts = {
		'(session/synchronize)': 'meta/synchronize',
		'(session/close)': 'session/close',
		'(session/save)': 'session/save',
		'(session/reset)': 'session/reset',
		'(screen/refresh)': 'session/screen/refresh',
		'(screen/resize)': 'session/screen/resize',

		'(frame/create)': 'session/frame/create',
		'(frame/copy)': 'session/frame/copy',
		'(frame/close)': 'session/frame/close',
		'(frame/previous)': 'session/frame/previous',
		'(frame/next)': 'session/frame/next',
		'(frame/switch)': 'session/frame/switch',
		'(frame/transpose)': 'session/frame/transpose',

		'(resource/switch)': 'session/resource/switch',
		'(resource/relocate)': 'session/resource/relocate',
		'(resource/open)': 'session/resource/open',
		'(resource/reload)': 'session/resource/reload',
		'(resource/save)': 'session/resource/write',
		'(resource/copy)': 'session/resource/copy',
		'(resource/close)': 'session/resource/close',

		# Resource Elements, lines.
		'(elements/undo)': 'delta/undo',
		'(elements/redo)': 'delta/redo',
		'(elements/select)': 'session/elements/transmit',
		'(elements/insert)': 'delta/insert/text',
		'(elements/delete)': 'delta/delete',
		'(elements/find)': 'navigation/session/search/resource',
		'(elements/next)': 'navigation/find/next',
		'(elements/previous)': 'navigation/find/previous',
	}

	def integrate(self, frame, refraction, key):
		"""
		# Process pending I/O events for display representation.

		# Called by (session/synchronize) instructions.
		"""

		# Acquire events prepared by &.system.IO.loop.
		events = self.io.take()
		rd = set()

		for io_context, io_transfer in events:
			# Apply the performed transfer using the &io_context.
			io_context.execute(io_transfer)
			rd.add(io_context.target.source.origin)

		# Presume updates are required.
		for resource_ref in rd:
			frame.deltas.extend(frame.refracting(resource_ref))

	def dispatch(self, frame, refraction, view, key):
		"""
		# Perform the application instruction identified by &key.
		"""

		try:
			if key in self.intercepts:
				# Mode independent application Instructions
				op_int = self.intercepts[key]
				ev_category, *ev_identifier = op_int.split('/')
				ev_identifier = tuple(ev_identifier)
				ev_args = ()
			else:
				# Key Translation
				mode, xev = self.keyboard.interpret(key)
				ev_category, ev_identifier, ev_args = xev

			ev_op = self.events[ev_category](ev_identifier)
			self.log(f"{key!r} -> {ev_category}/{'/'.join(ev_identifier)} -> {ev_op!r}")
			ev_op(self, frame, refraction, key, *ev_args) # User Event Operation
		except Exception as operror:
			self.keyboard.reset('control')
			self.error('Operation Failure', operror)
			del operror

		# Find parallel refractions that may require updates.
		yield from frame.refracting(refraction.source.origin, (refraction, view))
		if frame.deltas:
			for drf, dview in frame.deltas:
				yield from frame.refracting(drf.source.origin, (drf, dview))
			del frame.deltas[:]

	def cycle(self):
		"""
		# Process user events and execute differential updates.
		"""

		frame = self.focus
		device = self.device
		screen = device.screen

		status = list(frame.indicate(frame.focus, frame.view))
		restore = [(area, screen.select(area)) for area, _ in status]
		self.dispatch_delta(status)
		device.render_pixels()
		device.dispatch_frame()
		device.synchronize() # Wait for render queue to clear.

		for r in restore:
			screen.rewrite(*r)
			device.invalidate_cells(r[0])
		del restore, status

		try:
			# Synchronize input; this could be a timer or I/O.
			device.transfer_event()

			# Get the next event from the device. Blocking.
			key = device.key()

			for (rf, view) in self.dispatch(frame, frame.focus, frame.view, key):
				src = rf.source
				current = src.version()
				voffsets = [view.offset, view.horizontal_offset]
				if current != view.version or rf.visible != voffsets:
					self.dispatch_delta(rf.update(view, src.changes(view.version)))
					view.version = current
		except Exception as derror:
			self.error("Rendering Failure", derror)
			del derror

	def interact(self):
		"""
		# Dispatch the I/O service and execute &cycle until no frames exists.
		"""

		self.io.service()

		try:
			while self.frames:
				self.cycle()
		finally:
			self.store()
