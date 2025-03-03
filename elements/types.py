"""
# Supporting structures and types required by &.elements.
"""
import itertools
import collections

from dataclasses import dataclass
from fault.context import tools
from fault.syntax import format

from collections.abc import Sequence, Mapping, Iterable
from typing import Optional, Protocol, Literal, Callable

from ..cells import text
from ..cells.text import Phrase, Redirect, Words, Unit, Image
from ..cells.types import Area, Glyph, Pixels, Device, Line as LineStyle

class Core(object):
	"""
	# Core element type.

	# Common base class for all instructable application elements.
	"""

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

	def insert(self, offset, quantity):
		"""
		# Change the position to recognize that &quantity units at &offset
		# were added. Insertions within or adjacent to the range expand the range.
		"""

		position = self.get()
		if offset <= position:
			position += quantity

		if offset < self.datum:
			# Push range forward.
			self.datum += quantity
		else:
			# Range adjacent insertion, extend by quantity.
			if offset <= self.datum + self.magnitude:
				self.magnitude += quantity

		self.set(position)

	def delete(self, offset, quantity):
		"""
		# Change the position to recognize that &quantity units at &offset
		# were removed. Deletions that overlap with the range reduce its
		# size by the intersection.
		"""

		roffset = offset - self.datum
		end = roffset + quantity

		# Handle offset independently of the range.
		# Subsequent set()'s adjust accordingly.
		if self.offset >= roffset:
			# Offset is effected.
			if self.offset >= end:
				self.update(-quantity)
			else:
				self.offset = roffset
		position = self.get()

		if roffset >= self.magnitude:
			# Deletion entirely after range.
			return
		elif end < 0:
			# Deletion entirely before range.
			self.datum -= quantity
			self.set(position)
			return

		# Reduce magnitude by the overlapping area.
		assert end >= 0
		overlap = min(end, self.magnitude) - max(0, roffset)
		self.magnitude -= overlap

		if roffset > 0:
			# Deletion after datum, magnitude already reduced.
			return

		self.datum += roffset
		self.set(position)

	def changed(self, offset, quantity):
		"""
		# Adjust the position to accomodate for a change that occurred
		# to the reference space--insertion or removal.

		# Similar to &contract, but attempts to maintain &offset when possible,
		# and takes an absolute offset instead of a relative one.
		"""

		roffset = offset - self.datum

		if quantity > 0:
			return self.insert(offset, quantity)
		elif quantity < 0:
			return self.delete(offset, -quantity)

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

	def range(self, adjustment=0):
		"""
		# Construct a tuple pair noting the range of the cursor.
		"""

		start, pos, stop = map(adjustment.__add__, self.snapshot())
		return (start, stop)

@tools.struct()
class Status(object):
	"""
	# Descriptor providing details on the view's position, cursor location,
	# and the recent changes to the positions.
	"""

	focus: object
	# Copy area as it is possible for the focus to remain while its area changed.
	area: Area
	mode: str
	version: object
	cursor_line: Sequence[Glyph|Pixels]

	# View position.
	v_line_offset: int
	v_cell_offset: int

	# Cursor line offsets.
	ln_cursor_offset: int
	ln_range_start: int
	ln_range_stop: int

	# Cursor cell offsets.
	cl_cursor_start: int
	cl_cursor_stop: int
	cl_range_start: int
	cl_range_stop: int

	def line(self):
		return (
			self.ln_range_start,
			self.ln_cursor_offset,
			self.ln_range_stop,
		)

	def cell(self):
		return (
			self.cl_range_start,
			self.cl_cursor_start,
			self.cl_range_stop,
		)

	from dataclasses import astuple as _get_fields

	def __sub__(self, operand):
		p = [
			(None if i is o or i == o else o)
			for i, o in zip(self._get_fields()[:5], operand._get_fields()[:5])
		]

		d = (
			i - o
			for i, o in zip(self._get_fields()[5:], operand._get_fields()[5:])
		)
		return self.__class__(*p, *d)

	def __add__(self, operand):
		p = [
			o or i
			for i, o in zip(self._get_fields()[:5], operand._get_fields()[:5])
		]

		d = (
			i + o
			for i, o in zip(self._get_fields()[5:], operand._get_fields()[5:])
		)
		return self.__class__(*p, *d)

class Model(object):
	"""
	# The visual model defining the positions of panes.
	# Provides state for defining how a window's panes are positioned in an area,
	# methods for controlling position indicators, and rendering tools for
	# preparing drawing instructions.

	# Much of the functionality here could be isolated, but maintain the positioning
	# on the class for convenience and option for overloading.

	# [ Patterns ]
	# - `r_` prefixed methods generate instructions for performing rendering.
	# - `fm_`, Frame Model, prefixes usually refer to instance state or context.

	# [ Properties ]
	# /fm_deltas/
		# Mapping designating the size of a header, footer, or margin for a particular
		# division. Keyed with the vertical-division index pair.
	"""

	# Indicator images (characters) and colors.
	from . import symbols
	fm_iimages = {
		'left': {
			'leading': symbols.wedges['up'],
			'following': symbols.wedges['down'],
			'visible': symbols.wedges['right'],
			'reset-solid': symbols.lines['vertical'],
			'reset-weak': symbols.dotted['vertical'],
		},
		'right': {
			'leading': symbols.wedges['up'],
			'following': symbols.wedges['down'],
			'visible': symbols.wedges['left'],
			'reset-solid': symbols.lines['vertical'],
			'reset-weak': symbols.dotted['vertical'],
		},
		'top': {
			'leading': symbols.wedges['left'],
			'following': symbols.wedges['right'],
			'visible': symbols.wedges['down'],
			'reset-solid': symbols.lines['horizontal'],
			'reset-weak': symbols.dotted['horizontal'],
		},
		'bottom': {
			'leading': symbols.wedges['left'],
			'following': symbols.wedges['right'],
			'visible': symbols.wedges['up'],
			'reset-solid': symbols.lines['horizontal'],
			'reset-weak': symbols.dotted['horizontal'],
		},
	}

	def verticals(self):
		"""
		# Get the number of verticals.
		"""

		return len(self.fm_verticals)

	def divisions(self, vertical):
		"""
		# Get the number of divisions for the &vertical.
		"""

		return len(self.fm_divisions[vertical])

	def __init__(self, *, border=1, header=2, footer=0):
		self.fm_allocation = None
		self.fm_context = None
		self.fm_header_size = header
		self.fm_footer_size = footer
		self.fm_border_width = border
		self.fm_verticals = []
		self.fm_layout = []
		self.fm_divisions = collections.defaultdict(list)
		self.fm_deltas = {}
		self.fm_intersections = dict()

	def sole(self):
		"""
		# Initialize verticals and divisions as a sole area.
		"""

		self.fm_verticals = [
			((1, 1), (
				area.width - (self.fm_border_width * 2),
				area.height - (self.fm_border_width * 2),
			))
		]

		# Divisions(vertical separations).
		self.fm_divisions[0] = [self.fm_verticals[0] + ((2, 0),)]
		for k in self.fm_divisions:
			del self.fm_divisions[k]
		self.reset()

	def reset(self):
		"""
		# Reset caches derived from the grid's configuration.
		"""

		self.fm_intersections[:] = {
			(0, 0): symbols.corners['top-left'],
			(0, 3): symbols.intersections['left'],
			(self.fm_context.span-1, 3): symbols.intersections['right'],
			(self.fm_context.span-1, 0): symbols.corners['top-right'],
			(0, self.fm_context.lines-1): symbols.corners['bottom-left'],
			(self.fm_context.span-1, self.fm_context.lines-1): symbols.corners['bottom-right'],
		}

	def address(self, x, y):
		"""
		# Identify the vertical and division that contain the &x and &y coordinates.
		"""

		x -= self.fm_context.left_offset
		y -= self.fm_context.top_offset

		for v in range(len(self.fm_verticals)):
			p, d = self.fm_verticals[v]
			if x >= p[0] and x <= p[0] + d[0]:
				# Matched vertical.
				for i, (dp, dd, ds) in enumerate(self.fm_divisions[v]):
					if y >= dp[1] and y <= dp[1] + dd[1]:
						# Matched division.
						# Check Division Section
						ry = y - dp[1]

						if ds[0] and ry <= ds[0]:
							# Header
							s = 1
						elif ds[1] and ry >= dd[1] - ds[1]:
							# Footer
							s = 3
						else:
							s = 0

						return v, i, s

	@staticmethod
	def distribute(span:int, allocation:int, separator:int=1):
		"""
		# Distribute the available range in &span so that each division has at least the
		# requested &allocation.
		"""

		# Identify how many segments the span has room for.
		count = max(span // (allocation + separator), 1)

		# Identify the segment size available for the count.
		size = span // count

		# The multiple used to calculate the position.
		offset = size + separator

		# The size available to the last segment.
		last = span - (offset * (count-1))

		# Calculate the positions of the first available unit(after the border).
		return zip(
			(x+1 for x in map(offset.__mul__, range(count))),
			itertools.chain(
				itertools.repeat(size, count - 1),
				(last,)
			)
		)

	def redistribute(self, verticals, allocation=100):
		"""
		# Distribute the available vertical area so that each page has at least the
		# given &allocation.
		"""

		height = self.fm_context.lines - (self.fm_border_width * 2)
		width = self.fm_context.span - (self.fm_border_width * 2)
		nverticals = len(verticals)
		maxverticals = max(width // allocation, 1)
		units = sum(x[0] for x in verticals)
		if units < maxverticals:
			verticals.extend([(2, 1)] * maxverticalss - units)

		ralloc = width // maxverticals # remainder goes to last pane

		inheritor = nverticals - 1
		for i, va in enumerate(verticals):
			if va[1] == 0:
				# Override the vertical that receives the remaining space.
				inheritor = i
				break
		verticals[inheritor] = (verticals[inheritor][0], 0)
		self.fm_layout = verticals

		self.fm_verticals = [
			((None, 0 + self.fm_border_width), (allocation * x[1], height))
			for x in verticals
		]

		uwidth = width - sum(x[1][0] for x in self.fm_verticals)
		uwidth -= (nverticals - 1) * self.fm_border_width
		vp, vd = self.fm_verticals[inheritor]
		self.fm_verticals[inheritor] = (vp, (uwidth, vd[1]))

		# Calculate horizontal offsets using the calculated widths.
		offset = self.fm_border_width
		for i, v in enumerate(self.fm_verticals):
			self.fm_verticals[i] = ((offset, v[0][1]), v[1])
			offset += v[1][0]
			offset += self.fm_border_width

		# Reconstruct last record with updated width.
		for i, p in enumerate(self.fm_verticals):
			if i not in self.fm_divisions:
				self.fm_divisions[i] = [p + ((2, 0),)]
			self.update_inner_intersections(i)

		return len(self.fm_verticals)

	def set_margin_size(self, vertical, division, section, size):
		"""
		# Change the size of the header, footer, or left and right margins
		# for the division identified by &vertical and &division.
		"""

		key = (vertical, division, section)
		current = self.fm_deltas.get(key, 0)

		self.fm_deltas[key] = size
		vp, vd, vm = self.fm_divisions[vertical][division]
		if section == 1:
			h = size
			f = vm[1]
		elif section == 3:
			h = vm[0]
			f = size
		self.fm_divisions[vertical][division] = (vp, vd, (h, f))
		self.update_inner_intersections(vertical)

		return size - current

	def divide(self, page, divisions):
		"""
		# Split the page (vertical) into divisions
		"""

		pp, pd = self.fm_verticals[page]
		self.fm_divisions[page] = [
			((pp[0], p), (pd[0], height), (2, self.fm_deltas.get((page, di, 3), 0)))
			for di, (p, height) in enumerate(self.distribute(pd[1], (pd[1] // divisions)-1))
		]
		self.update_inner_intersections(page)

	def configure(self, area, divisions, allocation=100):
		"""
		# Configure the frame to have `len(divisions)` verticals where
		# each element describes the number of divisions within the vertical.
		"""

		self.fm_context = area
		self.fm_allocation = allocation
		self.redistribute(divisions, allocation)
		for i, vd in enumerate(divisions):
			self.divide(i, vd[0])
		return self

	@property
	def configuration(self):
		"""
		# The configured area and divisions.
		"""

		return self.fm_context, self.layout

	@property
	def layout(self):
		return self.fm_layout

	def iterpanes(self):
		"""
		# Identify the paths used to reach a given pane.
		"""

		for v in range(len(self.fm_verticals)):
			for d in range(len(self.fm_divisions[v])):
				yield (v, d)

	def itercontexts(self, terminal, *, section=0):
		"""
		# Construct Context instances for the configured set of panes
		# in left-to-right and top-to-bottom order.

		# [ Parameters ]
		# /section/
			# The portion of the pane to select.
			# Defaults to zero selecting the body.
		"""

		ry = self.fm_context.top_offset
		rx = self.fm_context.left_offset
		hborder = 1
		vborder = 1
		dt = 0
		db = 0
		dl = 0
		dr = 0
		alloc = (lambda CP, CD: (CP[1], CP[0], CD[1], CD[0]))

		# Clockwise: top, right, bottom, left
		if section == 0:
			# Body.
			position = (lambda: (rx+left+dl, ry+top+dt))
			dimensions = (lambda: (width-(dl+dr), height-(dt+db)))
		elif section == 1:
			# Header, priority over margins.
			# Left and right margins stop short of header.
			position = (lambda: (rx+left, ry+top))
			dimensions = (lambda: (width-dl-dr, dt-vborder))
		elif section == 2:
			# Right Margin.
			position = (lambda: (rx+left+width-dr+hborder, ry+top+dt))
			dimensions = (lambda: (dr-hborder, height-dt-db))
		elif section == 3:
			# Footer, priority over margins.
			# Left and right margins stop short of footer.
			position = (lambda: (rx+left, ry+top+height-(db-vborder)))
			dimensions = (lambda: (width, max(0, db-vborder)))
		elif section == 4:
			# Left Margin
			position = (lambda: (rx+left, ry+top+dt))
			dimensions = (lambda: (dl-hborder, height-dt-db))
		else:
			raise ValueError("five sections available in a pane, 0-4")

		for v in range(len(self.fm_verticals)):
			for cp, cd, cx in self.fm_divisions[v]:
				left, top = cp
				width, height = cd

				# Zeros unless a section is allocated.
				dt = cx[0] + vborder if cx[0] else 0
				db = cx[1] + vborder if cx[1] else 0

				yield alloc(position(), dimensions())

	@staticmethod
	def combine(f, l):
		"""
		# Combine box drawing characters to form intersections based on the glyph.
		"""

		match (f, l):
			# Left
			case ('│', '├') \
				| ('├', '│'):
				return '├'
			# Right
			case ('│', '┤') \
				| ('┤', '│'):
				return '┤'
			# Full
			case ('│', '─') \
				| ('├', '┤') \
				| ('┤', '├') \
				| ('┬', '┴') \
				| ('┴', '┬'):
				return '┼'

			# Select latter; handles (literal) corner cases.
			case (_):
				return l

	def update_inner_intersections(self, page):
		"""
		# Process the crossbars that divide a vertical.
		"""

		pp, pd = self.fm_verticals[page]
		li = '├'
		ri = '┤'

		# Collect the intersections using the divisions of the vertical.
		lefts = [(pp[0]-1, x[0][1]-1) for x in self.fm_divisions[page]]

		# Adjust for header. The intersections on the top are in the same position,
		# but are only half-down. The top and bottom are intentionally skipped
		# to be handled by another function.
		lefts[0] = (lefts[0][0], lefts[0][1] + 3) # Header

		# Adjust for right side.
		rights = [(x[0]+pd[0]+1, x[1]) for x in lefts]

		# Bottom is naturally skipped as only the start position of a division is considered.
		ixn = self.fm_intersections
		ixn.update((x, self.combine(li, ixn.get(x, li))) for x in lefts)
		ixn.update((x, self.combine(ri, ixn.get(x, ri))) for x in rights)

	def r_enclose(self, width, height):
		"""
		# Draw the surrounding frame of the session panes.
		"""

		symbols = self.symbols
		hlength = width - (self.fm_border_width * 2)
		vlength = height - (self.fm_border_width * 2)

		horiz = symbols.lines['horizontal']
		vert = symbols.lines['vertical']
		corners = symbols.corners

		# Horizontal top.
		yoffset = 0
		yield (yoffset, 0, 1, 1), corners['top-left']
		yield (yoffset, 1, 1, hlength), horiz
		yield (yoffset, width - 1, 1, 1), corners['top-right']

		# Horizontal bottom.
		yoffset = height - 1
		yield (yoffset, 0, 1, 1), corners['bottom-left']
		yield (yoffset, 1, 1, hlength), horiz
		yield (yoffset, width - 1, 1, 1), corners['bottom-right']

		# Verticals
		yield (1, 0, vlength, 1), vert
		yield (1, width-1, vlength, 1), vert

	def r_divide_verticals(self, position, size):
		"""
		# Render a vertical division.
		"""

		symbols = self.symbols
		top = symbols.intersections['top']
		bottom = symbols.intersections['bottom']
		vl = symbols.lines['vertical']
		left = symbols.intersections['left']
		right = symbols.intersections['right']
		full = symbols.intersections['full']
		hl = symbols.lines['horizontal']

		yield (position[1], position[0], 1, 1), top
		yield (position[1] + 1, position[0], size-2, 1), vl
		yield (position[1] + size - 1, position[0], 1, 1), bottom

	def r_divide_horizontals(self, solid, position, size):
		"""
		# Render a horizontal division.
		"""

		symbols = self.symbols
		end = (position[0] + size + 1, position[1])

		if solid:
			hl = symbols.lines['horizontal']
			li = self.fm_intersections.get(position, symbols.intersections['left'])
			ri = self.fm_intersections.get(end, symbols.intersections['right'])
		else:
			hl = symbols.dotted['horizontal']
			ri = li = symbols.lines['vertical']

		yield (position[1], position[0], 1, 1), li
		yield (position[1], position[0] + 1, 1, size), hl
		yield (position[1], position[0] + 1 + size, 1, 1), ri

	def r_patch_footer(self, vertical, division):
		"""
		# Render the dividing line used to separate the &section from the body.

		# Used when opening a prompt in an already drawn frame.
		"""

		vp, vd, vx = self.fm_divisions[vertical][division]
		header, footer = vx

		h = vp[0] - self.fm_border_width
		v = vp[1]

		yield from self.r_divide_horizontals(False,
			(h, v + vd[1] - footer - self.fm_border_width), vd[0])

	def r_divide(self, width, height):
		"""
		# Render all the divisions necessary to represent the model's configuration.

		# Performs the necessary &r_divide_verticals and &r_divide_horizontals
		# to represent the configured &fm_verticals and &fm_divisions.
		"""

		for vp, vd in self.fm_verticals[1:]:
			yield from self.r_divide_verticals((vp[0]-1, vp[1]-1), height)

		for i, v in enumerate(self.fm_verticals):
			for vp, vd, vx in self.fm_divisions[i][1:]:
				yield from self.r_divide_horizontals(True, (vp[0]-1, vp[1]-1), vd[0])

			for vp, vd, vx in self.fm_divisions[i]:
				header, footer = vx
				h = vp[0] - self.fm_border_width
				v = vp[1]

				if header:
					yield from self.r_divide_horizontals(False,
						(h, v + header), vd[0])
				if footer:
					yield from self.r_divide_horizontals(False,
						(h, v + vd[1] - footer - self.fm_border_width), vd[0])

	@staticmethod
	def indicate(itype, last, limit, offset, d, i):
		"""
		# Configure a position indicator using the given parameters to identify
		# the relative position that it should use, the indicator's type for color
		# selection, and the relative symbol name that should be used.
		"""

		# Color indicator for adjacency.
		if i == last and itype in {'offset-active'}:
			itype = 'stop-inclusive'

		# Apply delta, constrain range, and identify image reference.
		ri = i - d
		if ri < 0:
			# Minimum
			image = 'leading'
			ri = 0
		elif ri >= limit:
			# Maximum
			image = 'following'
			ri = limit - 1
		else:
			# Default color and symbol.
			image = 'visible'

		return itype, image, ri + offset

	@staticmethod
	def scale_ipositions(
			indicate,
			position, dimensions,
			horizontal, vertical, # Cursor Vectors
			dx, dy, # Cursor adjustments.
			*,
			borders=(1, 1),
			itypes=(
				'start-inclusive',
				'offset-active',
				'stop-exclusive',
			),
			zip=zip, R=itertools.repeat,
			chain=itertools.chain, rev=reversed,
		):
		"""
		# Annotate and scale the indicator positions in preparation for rendering.

		# [ Parameters ]
		# /position/
			# The &fm_context relative position of the pane.
		# /dimensions/
			# The width and height of the pane.
		# /horizontal/
			# The horizontal cursor positions to indicate.
		# /vertical/
			# The vertical cursor positions to indicate.
		# /dx/
			# The difference to apply to horizontals to adjust
			# for the view's positioning.
		# /dy/
			# The difference to apply to verticals to compensate
			# for the view's positioning.

		# [ Returns ]
		# #
			# - (control/type)`string`
			# - `top`
			# - `right`
			# - `bottom`
			# - `left`
		# # Cross Offset
		# # (type)&indicate
		"""

		borderx, bordery = borders
		h_offset = position[0] - borderx
		v_offset = position[1] - bordery

		h_limit = dimensions[0]
		v_limit = dimensions[1]

		# End of range, inclusive. Used to identify inclusive edge.
		h_last = horizontal[-1] - 1
		v_last = vertical[-1] - 1

		# Order is reversed on the opposing sides.
		# By changing the order, stacked indicators will have different
		# colors on each side allowing recognition of the intersection.

		v_context = R((v_last, v_limit, v_offset + bordery, dy))
		h_context = R((h_last, h_limit, h_offset + borderx, dx))

		# Left
		loffset = h_offset
		lpositions = zip(R('left'), R(loffset), v_context, vertical, itypes)

		# Right
		roffset = h_offset + borderx + h_limit
		rpositions = zip(R('right'), R(roffset), v_context, rev(vertical), rev(itypes))

		# Top
		toffset = v_offset
		tpositions = zip(R('top'), R(toffset), h_context, horizontal, itypes)

		# Bottom
		boffset = v_offset + bordery + v_limit
		bpositions = zip(R('bottom'), R(boffset), h_context, rev(horizontal), rev(itypes))

		# Dilate and transform.
		ip = chain(lpositions, rpositions, tpositions, bpositions)
		for (pv, coffset, i_context, xy, itype) in ip:
			if xy is None:
				continue
			yield pv, coffset, indicate(itype, *i_context, xy)

	def r_indicators(self, scaled, *, rtypes={}):
		"""
		# Render indicators from scaled positions.
		"""

		for pv, coffset, (itype, iimage, offset) in scaled:
			iis = self.fm_iimages[pv]
			ii = iis[iimage]

			match pv:
				case 'top' | 'bottom':
					position = (offset, coffset)
				case 'left' | 'right':
					position = (coffset, offset)

			if position in self.fm_intersections:
				re = self.fm_intersections[position]
			else:
				# Default horizontal or vertical. Dotted (weak) or solid.
				re = iis['reset-'+rtypes.get(pv, 'solid')]

			yield (position, itype, ii, re)

@tools.struct()
class System(object):
	"""
	# System context descriptor for dispatching operations in UNIX systems.

	# [ Elements ]
	# /sys_method/
		# Identifier for the method used to communicate with the system.
		# When using the local system APIs, this is `'system'`.
	# /sys_credentials/
		# Identifier for the entity that is dispatching operations in the system.
		# Empty string indicates that none are used.
	# /sys_authorization/
		# Supplemental identifier of authorization for dispatching system commands.
		# Usually an empty string. Formats as the password field when representing
		# the system context as a string.
	# /sys_identity/
		# Usually, the host name of the system's machine, real or virtual.
	# /sys_title/
		# An optional, user defined, label used to distinguish a system.

		# Sessions use &System instances to select &.element.Execution instances.
		# In cases where isolation or variation is desired by a user, the title
		# can be used to force a distinction to be made so that process sets can
		# be isolated without compromising one of the other fields.
	"""

	sys_method: str
	sys_credentials: str
	sys_authorization: str
	sys_identity: str
	sys_title: str = ''

	from dataclasses import replace as _replace

	def variant(self, system, *, Exceptions=set(['sys_title'])):
		"""
		# Whether &self is considered a variant of &system.
		"""

		return all([
			getattr(self, field) == getattr(system, field)
			for field in self.__dataclass_fields__.keys()
			if field not in Exceptions
		])

	def __str__(self):
		return ''.join(x[1] for x in self.i_format())

	def i_format(self, path:str|None=''):
		"""
		# Type qualified fields used to construct a string representing the system context.

		# [ Parameters ]
		# /path/
			# Override for the &sys_environment `'PWD'` value.
			# When &None, disable the path portion of the indicator.
		"""

		yield ('system-context', '')
		yield ('system-method', self.sys_method)
		yield ('delimiter', '://')

		if self.sys_credentials:
			yield ('system-credentials', self.sys_credentials)
			if self.sys_authorization:
				yield ('delimiter', ':')
				yield ('system-authorization', self.sys_authorization)
			yield ('delimiter', '@')

		yield ('system-identity', self.sys_identity)

		if self.sys_title:
			yield ('delimiter', '[')
			yield ('system-title', self.sys_title)
			yield ('delimiter', ']')

		if path is None:
			return

		if path[:1] == '/':
			yield ('delimiter', '/')
			path = path[1:]

		yield ('system-path', path)

	def retitle(self, title:str):
		"""
		# Construct an instance of the system, &self, with &title set as &sys_title.

		# [ Returns ]
		# New instance or &self when &self.sys_title equals &title.
		"""

		if self.sys_title == title:
			return self
		else:
			return self._replace(sys_title=title)

@tools.struct()
class Reference(object):
	"""
	# Resource identification and information.

	# [ Elements ]
	# /ref_system/
		# The system context that should be used to interact with the resource.
	# /ref_type/
		# The source of the selector used to get the syntax type from the session.
	# /ref_identity/
		# The source of the selector used to read and write the resource's elements.
	# /ref_context/
		# The filesystem context of the resource.
	# /ref_path/
		# The &ref_context relative path to the resource.
	"""

	ref_system: System
	ref_type: str
	ref_identity: str

	ref_context: object
	ref_path: object

	def i_format(self):
		"""
		# Type qualified fields used to construct a string representing the reference.
		"""

		yield from self.ref_system.i_format(str(self.ref_path))

	def __str__(self):
		return ''.join(x[1] for x in self.i_format())

	def retype(self, ref_type):
		"""
		# Reconstruct the reference with an updated type path.
		"""

		return self.__class__(
			self.ref_system,
			ref_type,
			self.ref_identity,
			self.ref_context,
			self.ref_path,
			self.ref_icons,
		)

@tools.struct()
class Line(object):
	"""
	# A structured line providing commonly required data for processing
	# by &Reformulations methods.

	# [ Elements ]
	# /ln_offset/
		# The index used to retrieve the line.
	# /ln_level/
		# The level of indentation that the content starts on.
	# /ln_content/
		# The text content of the line including any trailing whitespace.
	# /ln_extension/
		# Unstructured metadata associated with the line.
		# May define an override for &ln_type.
	"""

	ln_offset: int
	ln_level: int
	ln_content: str
	ln_extension: str = ''

	def i_format(self):
		yield ('delimiter', "(")
		yield ('line-number', str(self.ln_number))
		yield ('delimiter', "->")
		yield ('line-level', str(self.ln_level))
		yield ('delimiter', ": ")
		yield ('line-content', repr(self.ln_content))
		if self.ln_extension:
			yield ('delimiter', '+')
			yield ('line-extension', self.ln_extension)
		yield ('delimiter', ")")

	@property
	def ln_number(self) -> int:
		"""
		# The 1-based index of the line.
		"""

		return self.ln_offset + 1

	@property
	def ln_length(self) -> int:
		"""
		# The number of codepoints in &ln_content.
		# Temporarily includes &ln_level as tabs are integrated in raw strings.
		"""

		return len(self.ln_content)

	@property
	def ln_void(self) -> bool:
		"""
		# Whether the line has no content and no indentation.
		"""

		return not self.ln_level and not self.ln_content

	def prefix(self, string):
		"""
		# Reconstruct the line with the given string prepended to the content.
		"""

		return self.__class__(
			self.ln_offset,
			self.ln_level,
			string + self.ln_content,
			self.ln_extension,
		)

	def suffix(self, string):
		"""
		# Reconstruct the line with the given string appended to the content.
		"""

		return self.__class__(
			self.ln_offset,
			self.ln_level,
			self.ln_content + string,
			self.ln_extension,
		)

	def relevel(self, ilevel):
		"""
		# Reconstruct the line with the given indentation level.
		"""

		return self.__class__(
			self.ln_offset,
			ilevel,
			self.ln_content,
			self.ln_extension,
		)

	def ln_trailing(self, filter=str.isspace) -> int:
		"""
		# Count the trailing whitespace in &ln_content.

		# [ Parameters ]
		# /filter/
			# The false condition to look for at the end
			# of &ln_content. Defaults to &str.isspace.
		"""

		if not filter(self.ln_content[-1:]):
			return 0

		for i in range(-2, -(len(self.ln_content)+1), -1):
			if not filter(self.ln_content[i]):
				return (-i) - 1
		else:
			return len(self.ln_content)

	@property
	def ln_trail(self) -> str:
		"""
		# The trailing whitespace in &ln_content.

		# [ Returns ]
		# The whitespace codepoints or an empty string
		# if there are no trailing whitespace codepoints.
		"""

		lnc = self.ln_content
		tc = self.ln_trailing()
		if tc == 0:
			return ''

		return lnc[len(lnc)-tc:]

	def ln_count(self) -> int:
		"""
		# The number of lines.
		"""

		return 1

@tools.struct()
class Reformulations(object):
	"""
	# The set of I/O routines and descriptors for reading, writing, tokenizing,
	# formatting, and rendering a line of syntax.

	# Primarily used by syntax types, resources, and refractions to convert
	# a line from one form into another.

	# [ Elements ]
	# /lf_type/
		# The syntax type name.
	# /lf_theme/
		# The glyph templates used to compose Phrase instances from fields.
	# /lf_codec/
		# The encoding method used for reading and writing associated resources.
	# /lf_lines/
		# The formatting method used to identify line boundaries and
		# indentation levels.
	# /lf_fields/
		# The field isolation method for separating line content.
	# /lf_units/
		# The segmentation method for isolating the characters expressed
		# in a unicode codepoint sequence.
	"""

	from dataclasses import replace

	lf_type: str
	lf_theme: Mapping[str, Glyph]

	lf_codec: format.Characters
	lf_lines: format.Lines
	lf_fields: format.Fields
	lf_units: Callable[[str], Iterable[tuple[int, str]]]

	@property
	def lf_encoding(self) -> str:
		"""
		# Encoding identifier.
		"""

		return self.lf_codec.encoding

	@property
	def ln_content_offset(self):
		"""
		# The constant offset identifying where line content begins
		# in the elements of a Process Local Resource.

		# The size of the leading header specifying
		# the indentation level of the line and the size of the line extension.

		# - &ln_sequence
		# - &ln_structure
		"""

		return (4)

	def ln_sequence(self, ln:Line) -> str:
		"""
		# Construct the unicode codepoint representation of &ln
		# for storage as a Resource element.
		"""

		if ln.ln_extension:
			lxs = len(ln.ln_extension)
			lx_size = chr((lxs >> 14) & 0x7F) + chr((lxs >> 7) & 0x7F) + chr(lxs & 0x7F)
		else:
			lxs = 0
			lx_size = "\x00\x00\x00"

		return chr(ln.ln_level) + lx_size + ln.ln_content + ln.ln_extension

	def ln_interpret(self, linesrc:str, offset:int=-1, level:int=0) -> Line:
		"""
		# Interpret &linesrc as a structured line.
		"""

		return Line(offset, level, linesrc)

	def ln_structure(self, linestr:str, ln_offset=-1) -> Line:
		"""
		# Construct the structured Line instance from the unicode codepoint representation
		# used by Resource elements.
		"""

		il = ord(linestr[0]) # Indentation level.

		if linestr[1:(4)] == "\x00\x00\x00":
			# No extension.
			lxs = 0
			lx = ''
			lc = linestr[(4):]
		else:
			# Extension data.
			lxs = ord(linestr[1]) << 14 | ord(linestr[2]) << 7 | ord(linestr[3])
			lx = linestr[len(linestr)-lxs:]
			lc = linestr[(4):-len(lx)]

		return Line(ln_offset, il, lc, lx)

	def render(self, ilines:Iterable[Line]):
		"""
		# Construct &Phrase instances from the given &ilines.
		"""

		lines = list(ilines)
		return map(Phrase, (
			self.compose(li, fields)
			for li, fields in zip(
				lines,
				self.lf_fields.structure(lines),
			)
		))

	@staticmethod
	def interpret_line_form(Class, spec:str) -> format.Lines:
		"""
		# Parse the string representation of a line form
		# to create a &format.Lines instance for forming
		# &Line instances.
		"""

		# Symbolic terms for common whitespace characters.
		symbols = {
			'lf': '\n',
			'nl': '\n',
			'cr': '\c',
			'crlf': '\c\n',
			'tab': '\t',
			'ht': '\t',
			'sp': ' ',
		}

		termspec, indentspec = term.split('->')

		ilchar = indentspec.rstrip('0123456789')
		ilc = int(indentspec.rstrip(ilchar) or '1')

		t = symbols[termspec.lower()]
		i = symbols[ilchar] * ilc

		return format.Lines(t, i)

	@staticmethod
	def represent_line_form(linefmt: format.Lines) -> str:
		"""
		# Construct the string representation for identifying and
		# configuring the indented-line isolation method.
		"""

		symbols = {
			"\r": 'cr',
			"\r\n": 'crlf',
			"\n": 'lf',
			"\t": 'ht',
			" ": 'sp',
		}

		ilc = linefmt.indentation
		isym = symbols[ilc[:1]]
		tsym = symbols[linefmt.termination]

		# lf->ht or lf->sp4
		if len(ilc) > 1:
			ic = str(len(ilc))
		else:
			ic = ''

		return "->".join((tsym, isym+ic))

	def redirect_indentation(self, itype, il):
		"""
		# Special case control characters on the edges of line content.
		"""

		cf = self.lf_theme[itype]
		if itype == 'indentation-only':
			suffix = '>'
		else:
			suffix = ' '

		display = (' ' * 3) + suffix
		for c in range(il):
			yield Redirect((len(display), display, cf, '\t'))

	def redirect_trail(self, spaces):
		"""
		# Special case for trailing whitespace.
		"""

		cf = self.lf_theme['trailing-whitespace']
		for c in spaces:
			n = len(c)
			yield Redirect((n, n * '#', cf, c))

		# Final cell padding to eliminate vacant phrases.
		# The line feed is purely symbolic; annotation content can follow.
		lf = self.lf_theme['line-termination']
		yield Redirect((1, ' ', lf, '\n'))

	def redirect_exceptions(self, phrasewords, *,
			Unit=Unit,
			isinstance=isinstance,
			constants={
				0x1f: Redirect((1, '\u2038',
					Glyph(codepoint=ord('-'), textcolor=0x444444),
					"\x1f"
				))
			},
			obstruction=Glyph(codepoint=-1, textcolor=0x5050DF),
			representation=Glyph(codepoint=-1, textcolor=0x777777),
		):
		"""
		# Construct representations for control characters.
		"""

		for i in phrasewords:
			if len(i.text) == 1 and isinstance(i, Unit):
				o = ord(i.text)
				if o < 32:
					if o in constants:
						yield constants[o]
						continue

					d = hex(o)[2:].rjust(2, '0')
					yield Redirect((1, '[', obstruction, ''))
					yield Redirect((len(d), d, representation, i.text))
					yield Redirect((1, ']', obstruction, ''))
					continue
			yield i

	def segment(self, fields):
		"""
		# Construct a segmented phrase from the given fields.
		"""

		tg = self.lf_theme.get
		return Phrase.segment(
			(tg(ft, ft), self.lf_units(fc))
			for ft, fc in fields
		)

	def cursor(self, line, fields) -> Iterable[Words]:
		"""
		# Construct a Phrase instance representing the structured line
		# for display with a cursor.
		"""

		tg = self.lf_theme.get # Returns the requested key for already resolved Cells.

		if line.ln_content:
			itype = 'indentation'
		else:
			itype = 'indentation-only'

		content = Phrase.segment(
			(tg(ft, ft), self.lf_units(fc))
			for ft, fc in fields
		)

		yield from self.redirect_indentation(itype, line.ln_level)
		yield from self.redirect_exceptions(content)
		yield Redirect((1, ' ', tg('line-termination'), '\n'))

	def compose(self, line, fields) -> Iterable[Words]:
		"""
		# Construct a Phrase instance representing the structured line.
		"""

		tg = self.lf_theme.get # Returns the requested key for already resolved Cells.

		if line.ln_content:
			itype = 'indentation'
		else:
			itype = 'indentation-only'

		sfields = list(fields)
		if sfields:
			# Strip trailing whitespace.
			sfields[-1] = (
				sfields[-1][0],
				sfields[-1][1].rstrip()
			)

		content = Phrase.segment(
			(tg(ft, ft), self.lf_units(fc))
			for ft, fc in sfields
		)

		yield from self.redirect_indentation(itype, line.ln_level)
		yield from self.redirect_exceptions(content)
		yield from self.redirect_trail(line.ln_trail)

	def __str__(self):
		return ''.join(x[1] for x in self.i_format())

	def i_format(self):
		yield ('scheme', 'syntax')
		yield ('delimiter', '://')
		yield ('syntax-type', self.lf_type)
		yield ('delimiter', '/')
		yield ('syntax-line-form', self.represent_line_form(self.lf_lines))
		yield ('delimiter', '/')
		yield ('syntax-character-encoding', self.lf_encoding)
