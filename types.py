"""
# Data structures for supporting the manipulation of text in an &.edit.Session instance.
"""
import itertools
from typing import Optional, Protocol

from dataclasses import dataclass
from fault.context import tools
from fault.terminal import matrix

from collections.abc import Sequence
from collections.abc import Mapping

from . import alignment

class Annotation(Protocol):
	"""
	# Interface for cursor annotation status displays conveying additional
	# information regarding an identified subject with respect to some
	# connected information context.
	"""

	def close(self):
		"""
		# Signal end of use.
		"""

	def update(self, refraction):
		"""
		# Adjust the annotation to accommodate for &refraction state changes.
		"""

	def rotate(self, quantity=1):
		"""
		# Cycle through the list of representations to be displayed.
		"""

	def insertion(self) -> str:
		"""
		# Get the &str that should be inserted if a capture operation were performed.
		# Primarily for completion, but applicable to other annotations.
		"""

	def image(self) -> object:
		"""
		# Get the primary structured fields representing the state of the annotation.
		# Usually this contains the &insertion in part or whole, but is always
		# implementation dependent.
		"""

class Position(object):
	"""
	# Mutable position state for managing the position of a cursor with respect to a range.
	# No constraints are enforced and position coherency is considered subjective.

	# [ Properties ]
	# /datum/
		# The absolute reference position. (start)
	# /offset/
		# The actual position relative to the &datum. (current=datum+offset)
	# /magnitude/
		# The size of the range relative to the &datum. (stop=datum+magnitude)
	"""

	@property
	def minimum(self):
		return self.datum

	@property
	def maximum(self):
		return self.datum + self.magnitude

	def __init__(self):
		self.datum = 0 # physical position
		self.offset = 0 # offset from datum (0 is minimum)
		self.magnitude = 0 # offset from datum (maximum of offset)

	def get(self):
		"""
		# Get the absolute position.
		"""

		return self.datum + self.offset

	def set(self, position):
		"""
		# Set the absolute position.

		# Calculates a new &offset based on the absolute &position.

		# [ Returns ]
		# The change that was applied to the offset.
		"""

		new = position - self.datum
		change = self.offset - new
		self.offset = new
		return change

	def configure(self, datum, magnitude, offset = 0):
		"""
		# Initialize the values of the position.
		"""

		self.datum = datum
		self.magnitude = magnitude
		self.offset = offset

	def limit(self, minimum, maximum):
		"""
		# Apply the minimum and maximum limits to the Position's absolute values.
		"""

		l = [
			minimum if x < minimum else (
				maximum if x > maximum else x
			)
			for x in self.snapshot()
		]
		self.restore(l)

	def constrain(self):
		"""
		# Adjust the offset to be within the bounds of the magnitude.
		# Returns the change in position; positive values means that
		# the magnitude was being exceeded and negative values
		# mean that the minimum was being exceeded.
		"""

		o = self.offset
		if o > self.magnitude:
			self.offset = self.magnitude
		elif o < 0:
			self.offset = 0

		return o - self.offset

	def snapshot(self):
		"""
		# Calculate and return the absolute position as a triple.
		"""

		start = self.datum
		offset = start + self.offset
		stop = start + self.magnitude
		return (start, offset, stop)

	def restore(self, snapshot):
		"""
		# Restores the given snapshot.
		"""

		self.datum = snapshot[0]
		self.offset = snapshot[1] - snapshot[0]
		self.magnitude = snapshot[2] - snapshot[0]

	def update(self, quantity):
		"""
		# Update the offset by the given quantity.
		# Negative quantities move the offset down.
		"""

		self.offset += quantity

	def clear(self):
		"""
		# Reset the position state to a zeros.
		"""

		self.__init__()

	def zero(self):
		"""
		# Zero the &offset and &magnitude of the position.

		# The &datum is not changed.
		"""

		self.magnitude = 0
		self.offset = 0

	def move(self, location=0, perspective=0):
		"""
		# Move the position relatively or absolutely.

		# Perspective is like the whence parameter, but uses slightly different values.

		# `-1` is used to move the offset relative from the end.
		# `+1` is used to move the offset relative to the beginning.
		# Zero moves the offset relatively with &update.
		"""

		if perspective == 0:
			self.offset += location
			return location

		if perspective > 0:
			offset = 0
		else:
			# negative
			offset = self.magnitude

		offset += (location * perspective)
		change = self.offset - offset
		self.offset = offset

		return change

	def collapse(self):
		"""
		# Move the origin to the position of the offset and zero out magnitude.
		"""

		o = self.offset
		self.datum += o
		self.offset = self.magnitude = 0
		return o

	def normalize(self):
		"""
		# Relocate the origin, datum, to the offset and zero the magnitude and offset.
		"""

		if self.offset >= self.magnitude or self.offset < 0:
			o = self.offset
			self.datum += o
			self.magnitude = 0
			self.offset = 0
			return o
		return 0

	def reposition(self, offset = 0):
		"""
		# Reposition the &datum such that &offset will be equal to the given parameter.

		# The magnitude is untouched. The change to the origin, &datum, is returned.
		"""

		delta = self.offset - offset
		self.datum += delta
		self.offset = offset
		return delta

	def start(self):
		"""
		# Start the position by adjusting the &datum to match the position of the &offset.
		# The magnitude will also be adjust to maintain its position.
		"""

		change = self.reposition()
		self.magnitude -= change

	def bisect(self):
		"""
		# Place the position in the middle of the start and stop positions.
		"""

		self.offset = self.magnitude // 2

	def halt(self, delta=0):
		"""
		# Halt the position by adjusting the &magnitude to match the position of the
		# offset.
		"""

		self.magnitude = self.offset + delta

	def invert(self):
		"""
		# Invert the position; causes the direction to change.
		"""

		self.datum += self.magnitude
		self.offset = -self.offset
		self.magnitude = -self.magnitude

	def page(self, quantity = 0):
		"""
		# Adjust the position's datum to be at the magnitude's position according
		# to the given quantity. Essentially, this is used to "page" the position;
		# a given quantity selects how far forward or backwards the origin is sent.
		"""

		self.datum += (self.magnitude * quantity)

	def dilate(self, offset, quantity):
		"""
		# Adjust, increase, the magnitude relative to a particular offset.
		"""

		return self.contract(offset, -quantity)

	def contract(self, offset, quantity):
		"""
		# Adjust, decrease, the magnitude relative to a particular offset.
		"""

		if offset < 0:
			# before range; offset is relative to datum, so only adjust datum
			self.datum -= quantity
		elif offset <= self.magnitude:
			# within range, adjust size and position
			self.magnitude -= quantity
			self.offset -= quantity
		else:
			# After of range, so only adjust offset
			self.offset -= quantity

	def changed(self, offset, quantity):
		"""
		# Adjust the position to accomodate for a change that occurred
		# to the reference space--insertion or removal.

		# Similar to &contract, but attempts to maintain &offset when possible,
		# and takes an absolute offset instead of a relative one.
		"""

		roffset = offset - self.datum

		if roffset < 0:
			# Offset indirectly updated by datum's change.
			self.datum += quantity
		elif roffset > self.magnitude:
			self.update(quantity)
		else:
			self.update(quantity)
			self.magnitude += quantity

	def relation(self):
		"""
		# Return the relation of the offset to the datum and the magnitude.
		"""

		o = self.offset
		if o < 0:
			return -1
		elif o > self.magnitude:
			return 1
		else:
			return 0 # within bounds

	def compensate(self):
		"""
		# If the position lay outside of the range, relocate
		# the start or stop to be on position.
		"""

		r = self.relation()
		if r == 1:
			self.magnitude = self.offset
		elif r == -1:
			self.datum += self.offset
			self.offset = 0

	def slice(self, adjustment=0, step=1, Slice=slice):
		"""
		# Construct a &slice object that represents the range.
		"""

		start, pos, stop = map(adjustment.__add__, self.snapshot())
		return Slice(start, stop, step)

@tools.struct()
class Reference(object):
	"""
	# Resource identification and information.

	# [ Elements ]
	# /ref_type/
		# The source of the selector used to read the syntax type.
	# /ref_identity/
		# The source of the selector used to read the resource's elements.
	# /ref_context/
		# The context of the resource. Often current working directory or project directory.
	# /ref_path/
		# The &ref_context relative path to the resource.
	# /ref_icons/
		# Mapping of &Reference field names, without the `ref_` prefix, to
		# phrases that represent the associated symbolism within a two-cell
		# area.
	"""

	ref_type: str
	ref_identity: str

	ref_context: object
	ref_path: object

	ref_icons: Mapping[str, matrix.Context.Phrase]|None

	def retype(self, ref_type):
		"""
		# Reconstruct the reference with an updated type path.
		"""
		self.__class__(
			ref_type,
			self.ref_identity,
			self.ref_context,
			self.ref_path,
			self.ref_icons,
		)

class Refraction(object):
	"""
	# The elements and status of a selected resource.

	# [ Elements ]
	# /origin/
		# Reference identifying the resource being refracted.
	# /type/
		# Type identifier used to select the &structure.
	# /structure/
		# The field sequence constructor for identifying how
		# the &elements should be represented on within a &View.
	# /format/
		# The structured line processor formatting the fields
		# into a &matrix.Context.Phrase.
	# /annotation/
		# Field annotation state.
	# /elements/
		# The contents of the connected resource.
		# The sequence of lines being refracted.
	# /log/
		# The changes applied to &elements.
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
		# &.keyboard.Selection intercepts will eliminate the need for this.
	"""

	origin: Reference
	structure: object
	format: object
	render: object
	annotation: Optional[Annotation]
	elements: Sequence[object]
	log: object
	focus: Sequence[object]
	limits: Sequence[int]
	visible: Sequence[int]
	activate = None
	cancel = None

	def current(self, depth):
		d = self.elements
		for i in range(depth):
			f = self.focus[i]
			fi = f.get()
			if fi < len(d):
				d = d[f.get()]
			else:
				return ""
		return d or ""

	def retype(self, type, structure, format, render):
		"""
		# Reconstruct &self with a new syntax type.
		"""

		new = object.__new__(self.__class__)
		new.__dict__.update(self.__dict__.items())
		new.type = type
		new.structure = structure
		new.format = format
		new.render = render

		return new

	def __init__(self, origin, type, structure, format, render, elements, log):
		# Context, but with caching layers.
		self.origin = origin
		self.type = type
		self.structure = structure
		self.format = format
		self.render = render
		self.annotation = None

		# State. Document elements, cursor, and camera.
		self.elements = elements
		self.log = log

		self.focus = (Position(), Position())
		self.visibility = (Position(), Position())
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
		width, height = dimensions

		vv.magnitude = height
		hv.magnitdue = width
		vv.offset = min(12, height // 12) or -1 # Vertical, align with elements.
		hv.offset = min(6, width // 20) or -1

		self.limits = (vv.offset, hv.offset)
		self.dimensions = dimensions

		return self

	def view(self):
		return len(self.elements), self.dimensions[1], self.visible[1]

	def scroll(self, delta):
		"""
		# Apply the &delta to the vertical position of the primary dimension changing
		# the set of visible elements.
		"""

		to = delta(self.visible[0])
		if to < 0:
			to = 0
		else:
			last = len(self.elements) - self.dimensions[1]
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
			ilines = self.elements.select(*area)

			for lo, line in zip(range(start, stop, d), ilines):
				i = fmethod(line, string, *srange)
				if i == -1:
					# Not in this line.
					srange = (0, None)
					continue
				else:
					v.set(lo)
					self.vertical_changed(lo)
					h.restore((i, i, i + termlength))
					return

	def seek(self, element, unit):
		"""
		# Relocate the cursor to the &unit in &element.
		"""

		self.focus[0].set(element)
		self.focus[1].set(unit if unit is not None else len(self.elements[element]))
		page_offset = element - (self.dimensions[1] // 2)
		self.scroll(lambda x: page_offset)

	def usage(self):
		"""
		# Calculate the resource, memory, usage of the refraction.
		"""

		return self.log.usage() + self.elements.usage()

	def delta(self, offset, change, *, max=max,
			ainsert=alignment.insert,
			adelete=alignment.delete,
		):
		"""
		# Adjust view positioning to compensate for changes in &elements.

		# Must be executed prior to the &change being applied.
		"""

		total = len(self.elements)
		if change > 0:
			op = ainsert
			sign = +1
		else:
			op = adelete
			sign = -1

		for rf, v in getattr(self, 'parallels', ((self, None),)):
			position = rf.visible[0]
			visible = rf.dimensions[1]
			rf.visible[0] = op(total, visible, position, offset, sign*change)

		return self

	from . format import Whitespace
	def vertical_changed(self, ln, *, lil=Whitespace.il,
			backward=alignment.backward,
			forward=alignment.forward,
		):
		"""
		# Constrain the focus and apply margin scrolls.
		"""

		total = len(self.elements)

		# Constrain vertical and identify indentation level (bol).
		try:
			line = self.elements[ln]
		except IndexError:
			line = ""
			ll = 0
			bol = 0
			if ln >= total or ln < 0:
				# Constrain vertical; may be zero.
				self.focus[0].set(total)
		else:
			ll = len(line)
			bol = lil(line)

		# Constrain cursor.
		h = self.focus[1]
		h.datum = max(bol, h.datum)
		h.magnitude = min(ll, h.magnitude)
		h.set(min(ll, max(bol, h.get())))
		assert h.get() >= 0 and h.get() <= ll

		# Margin scrolling.
		current = self.visible[0]
		rln = ln - current
		climit = max(0, self.limits[0])
		sunit = max(1, climit * 2)
		edge = self.dimensions[1]
		if rln <= climit:
			# Backwards
			position, rscroll, area = backward(total, edge, current, sunit)
			if ln < position:
				self.visible[0] = max(0, ln - (edge // 2))
			else:
				self.visible[0] = position
		else:
			if rln >= edge - climit:
				# Forwards
				position, rscroll, area = forward(total, edge, current, sunit)
				if not (position + edge) > ln:
					self.visible[0] = min(total - edge, ln - (edge // 2))
				else:
					self.visible[0] = position

	del Whitespace

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

		fs = self.structure(self.elements[element])
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
			fi = -1

		t = areas[fi]
		return fi, t

	def field(self, quantity):
		return self.field_select(quantity)[1]

	def unit(self, quantity):
		# Find the current position.
		h = self.focus[1].get()
		phrase = self.render(self.current(1))
		p, r = phrase.seek((0, 0), h)
		assert r == 0

		# Find the codepoint offset after the Character Unit at &p
		np, r = phrase.seek(p, quantity, *phrase.m_unit)
		return phrase.tell(np, *phrase.m_codepoint)

@dataclass(match_args=False, eq=False)
class View(object):
	"""
	# A displayed view of a &Refraction.

	# [ Elements ]
	# /display/
		# The graphics environment that renders the &image.
	# /image/
		# Phrase sequence to be rendered to the &display.
	# /whence/
		# The beginning of each phrase in &image.
		# `assert len(image) == len(whence)`
	# /edges/
		# The border type that is expected to be drawn around the &display.
		# Used to restore the proper border character when frame indicators
		# are reset.
	# /version/
		# The identifier of the Log commit that is currently being represented in &image. (when)
	# /offset/
		# The identifier of the element that is first seen in &image. (where)
	"""

	# Placeholder insertion used to compensate for image changes.
	Empty = matrix.Context.Phrase([
		matrix.Context.Words((0, "", matrix.Context.RenderParameters(
			(matrix.Context.Traits(0), -1024, -1024, -1024)
		)))
	])

	display: matrix.Context
	image: Sequence[matrix.Context.Phrase]
	whence: Sequence[tuple[tuple[int,int], int]]
	edges: Mapping[str, str]
	version: object = (0, 0, None)
	offset: int = 0
	horizontal_offset = 0

	def update(self, area, phrases):
		"""
		# Set the given &phrases to the designated &area of &image.
		"""

		self.image[area] = phrases
		self.whence[area] = [
			ph.seek((0, 0), self.horizontal_offset, *ph.m_cell)
			for ph in phrases
		]

	def truncate(self):
		"""
		# Delete the phrases cached in &image.
		"""
		del self.image[:]
		del self.whence[:]

	def trim(self):
		"""
		# Limit the image to the display's height.
		"""

		d = self.display.height
		del self.image[d:]
		del self.whence[d:]

		assert len(self.image) == self.display.height
		assert len(self.whence) == self.display.height

	def compensate(self):
		"""
		# Extend the image with &Empty lines until the display is filled.
		"""

		# Pad end with empty lines.
		start = len(self.image)
		d = self.display.height - start
		self.image.extend([self.Empty] * d)
		self.whence.extend([((0, 0), 0)] * d)

		assert len(self.image) == self.display.height
		assert len(self.whence) == self.display.height
		yield from self.render(slice(start, len(self.image)))

	def renderline(self, offset, phrase):
		"""
		# Sequence the necessary display instructions for rendering
		# a single line.
		"""

		context = self.display
		limit = context.width
		rtx = context.reset_text()

		yield rtx
		yield context.seek((0, offset))
		yield from context.render(phrase)

		# Erase to margin.
		void_cells = context.width - phrase.cellcount()
		if void_cells > 0:
			yield context.erase(void_cells)
		yield rtx

	def render(self, area):
		"""
		# Sequence the necessary display instructions for rendering
		# the &area reflecting the current &image state.
		"""

		context = self.display
		limit = context.width
		voffset = area.start or 0 # Context seek offset.
		hoffset = self.horizontal_offset
		rtx = context.reset_text()

		yield rtx
		for (phrase, w) in zip(self.image[area], self.whence[area]):
			yield context.seek((0, voffset))
			yield from context.render(context.view(phrase, *w, limit))
			visible = max(0, phrase.cellcount() - hoffset)
			void_cells = limit - visible
			if void_cells > 0:
				yield context.erase(void_cells)
			yield rtx
			voffset += 1

	def vertical(self, rf):
		v = rf.visible[0]
		return slice(v, v+self.display.height, 1)

	def horizontal(self, rf):
		h = rf.visible[1]
		return slice(h, h+self.display.width, 1)

	def pan_relative(self, area, offset, *, islice=itertools.islice):
		"""
		# Update the image's whence column by advancing the positions with &offset.
		# The seek is performed relative to the current positions.
		"""

		wcopy = self.whence[area]
		ipairs = zip(wcopy, islice(self.image, area.start, area.stop))
		self.whence[area] = (
			ph.seek(w[0], offset-w[1], *ph.m_cell)
			for w, ph in ipairs
		)

	def pan_absolute(self, area, offset, *, islice=itertools.islice):
		"""
		# Update the &whence of the phrases identified by &area.
		# The seek is performed relative to the beginning of the phrase.
		"""

		wcopy = self.whence[area]
		ipairs = zip(wcopy, islice(self.image, area.start, area.stop))
		self.whence[area] = (
			ph.seek((0, 0), offset, *ph.m_cell)
			for w, ph in ipairs
		)

	def prefix(self, phrases):
		"""
		# Insert &phrases at the start of the image and adjust the offset
		# by the number inserted.

		# [ Returns ]
		# Slice to be updated.
		"""

		count = len(phrases)
		self.image[0:0] = phrases
		self.whence[0:0] = [((0, 0), 0) for x in range(len(phrases))]
		self.offset -= count

		area = slice(0, len(phrases))
		if self.horizontal_offset:
			self.pan_absolute(area, self.horizontal_offset)
		return area

	def suffix(self, phrases):
		"""
		# Insert &phrases at the end of the image and return the &slice
		# that needs to be updated.

		# [ Returns ]
		# Slice to be updated.
		"""

		count = len(phrases)
		il = len(self.image)
		self.image.extend(phrases)
		self.whence.extend([((0, 0), 0)] * count)

		area = slice(il, il + count)
		if self.horizontal_offset:
			self.pan_absolute(area, self.horizontal_offset)
		return area

	def delete(self, index, count):
		"""
		# Remove &count elements at the view relative &index.

		# [ Returns ]
		# Slice to the deleted area needing to be updated.
		"""

		stop = index + count
		isize = len(self.image)
		del self.image[index:stop]
		del self.whence[index:stop]

		return slice(index, stop)

	def insert(self, index, count):
		"""
		# Insert &count empty phrases at the view relative &index.

		# [ Returns ]
		# Slice to the inserted area needing to be updated.
		"""

		self.image[index:index] = [self.Empty] * count
		self.whence[index:index] = [((0, 0), 0)] * count

		area = slice(index, index + count)
		if self.horizontal_offset:
			self.pan_absolute(area, self.horizontal_offset)
		return area
