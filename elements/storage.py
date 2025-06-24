"""
# Process local resources.

# &Resource implementation and supporting functionality.
"""
from collections.abc import Sequence, Iterable, Mapping
import collections
import itertools
import weakref

from fault.syntax import delta
from fault.syntax import sequence

from . import types

##
# The line content offset is hardcoded to avoid references, but are
# parenthesized so that substitution may be performed if changes are needed.
class Resource(types.Core):
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
	"""

	origin: types.Reference
	forms: types.Reformulations

	elements: Sequence[str]
	modifications: delta.Log

	status: object
	views: object

	def __init__(self, origin, forms):
		self.origin = origin
		self.forms = forms

		self.elements = sequence.Segments([])
		self.modifications = delta.Log()
		self.snapshot = self.modifications.snapshot()
		self.status = None
		self.views = weakref.WeakSet()
		self.cursors = weakref.WeakSet()

	def usage(self):
		try:
			eusage = self.elements.usage
		except AttributeError:
			# Presume list.
			yield self.elements
			yield from self.elements
		else:
			yield from eusage()

		yield from self.modifications.usage()

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

		self._commit(self.modifications.undo(quantity))

	def redo(self, quantity=1):
		"""
		# Replay modifications until the next checkpoint is reached.
		"""

		self._commit(self.modifications.redo(quantity))

	def _commit(self, deltas):
		"""
		# Apply pending modifications.
		"""

		slog = self.modifications
		views = list(self.views)
		srclines = self.elements

		for dsrc in deltas:
			dsrc.apply(srclines)
			if self.cursors:
				for c in self.cursors:
					dsrc.track(c)

			for rf in views:
				dsrc.track(rf)
				df = list(rf.v_update(dsrc))
				if rf.frame_visible:
					# Update all image states, but don't dispatch to the display
					# if it's not frame_visible.
					rf.deltas.extend(df)

		for rf in views:
			rf.recursor()

		return slog

	def commit(self, collapse=True, checkpoint=False):
		"""
		# Apply pending modifications.
		"""

		l = self._commit(list(self.modifications.pending()))

		if collapse:
			l.collapse()

		l.commit()

		if checkpoint:
			l.checkpoint()

		return l

	def checkpoint(self, collapse=True):
		"""
		# Apply, commit, and checkpoint the log.
		"""

		return self.commit(collapse=collapse, checkpoint=True)

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

		li = self.sole(lo)
		lines = list(self.select(lo+1, lo+1+count))
		combined = withstring + withstring.join(li.ln_content for li in lines)

		(self.modifications
			.write(delta.Update(lo, combined, "", (4) + len(li.ln_content)))
			.write(delta.Lines(lo+1, [], list(self.elements[lo+1:lo+1+count]))))

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

	def displace_cursors(self, lo, ln_count, co, cp_count):
		"""
		# Insert a &delta.Cursor record causing the cursor to move
		# in the context of a commit.
		"""

		# co+(4) for parity with regular changes.
		(self.modifications
			.write(delta.Cursor(lo, ln_count, co+(4), cp_count)))

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
		try:
			target_line = self.sole(lo)
		except IndexError:
			if lo > self.ln_count():
				raise

			# Allow initialization at end of file.
			self.ln_initialize(offset=lo)
			self.commit()
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
			end_of_insert = len(wholes[-1])
			wholes[-1] = wholes[-1] + suffix

			# Force cursors at &lo to beginning of next line.
			eol = co + len(fcontent)
			# Codepoint offset must be zero here. Otherwise, deletion is
			# identified as occurring past the cursor.
			self.displace_cursors(lo, +1, 0, -eol)

			# Identify indentation boundaries and structure the line.
			ln_i = self.forms.ln_interpret # Universal
			llines = map(level_line, wholes)
			slines = list(ln_i(ls, level=(ln_level+il if ls else il)) for il, ls in llines)

			# Insert and identify the new codepoint offset in the final line.
			dl = self.insert_lines(lo+1, slines)
			co = slines[-1].ln_length - len(suffix)

			# Restore cursors that were offset.
			self.displace_cursors(lo+dl, -1, 0, 0)
			self.displace_cursors(lo+dl, 0, 0, end_of_insert)
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

	def truncate(self):
		"""
		# Remove all lines.

		# [ Returns ]
		# The number of lines removed.
		"""

		lines = self.delete_lines(0, self.ln_count())
		self.ln_initialize()

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

	@comethod('deltas', 'undo')
	def d_undo(self, quantity=1):
		self.undo(quantity)

	@comethod('deltas', 'redo')
	def d_redo(self, quantity=1):
		self.redo(quantity)

	@comethod('deltas', 'truncate')
	def d_truncate(self, quantity=None):
		self.modifications.truncate(quantity)
		rv = self.modifications.snapshot()
		for rf in self.views:
			rf.version = rv

	@comethod('resource', 'repartition')
	def r_repartition(self):
		self.elements.partition()

	@comethod('resource', 'save')
	def r_save(self, rl_syntax, session, content):
		system, fspath = rl_syntax.location_path()
		return system.store_resource(session.log, content.source, content)

	@comethod('resource', 'copy')
	def r_copy_resource(self, log, text, system, files):
		url = text
		if not url.startswith('/'):
			raise ValueError("not a filesystem path: " + url) # Expects an absolute path.

		re = self.origin.ref_path@url
		src = files.allocate_resource(system.reference(self.origin.ref_type, re), self.forms)
		src.elements = self.elements
		if src.origin.ref_path.fs_type() != 'void':
			src.status = src.origin.ref_path.fs_status()

		system.store_resource(log, src)

class Directory(types.Core):
	"""
	# Collection of process local resources, normally, held by a session.

	# A nearly pointless abstraction to a mapping for binding instructions
	# and isolating resource management methods.

	# The directory of files is stored as a flat mapping and may refer
	# to resources across multiple filesystems.
	"""

	resources: Mapping[str, Resource]

	def __init__(self, Type=dict):
		self.resources = Type()

	def allocate_resource(self, ref:types.Reference, syntax_type) -> Resource:
		"""
		# Create a &Resource instance using the given reference as it's origin.

		# Does not change the state of the collection.
		"""

		return Resource(ref, syntax_type)

	def create_resource(self, system, typref, syntype, path) -> Resource:
		"""
		# Create an empty &Resource associated with &path and
		# add it to the resource set managed by &self.
		"""

		if path in self.resources:
			return self.resources[path]

		ref = types.Reference(
			system,
			typref,
			str(path),
			path.context or path ** 1,
			path
		)

		src = self.allocate_resource(ref, syntype)
		self.insert_resource(src)
		src.ln_initialize()
		src.commit()

		return src

	def list_resources(self, Type=list) -> list[Resource]:
		"""
		# Construct a new list containing reference copies of all the resources.
		"""

		return Type(self.resources.items())

	def select_resource(self, path):
		"""
		# Get the &Resource instance associated with &path in the collection.
		"""

		return self.resources[path]

	def insert_resource(self, source:Resource):
		"""
		# Add &source to the collection of files.
		"""

		self.resources[source.origin.ref_path] = source

	def delete_resource(self, source:Resource):
		"""
		# Remove &source from the collection.
		"""

		del self.resources[source.origin.ref_path]
