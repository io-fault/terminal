"""
# Supporting structures and types required by &.elements.
"""
import itertools
import collections
import weakref

from dataclasses import dataclass
from fault.context import comethod
from fault.context import tools
from fault.syntax import format
from fault.internet import ri

from collections.abc import Sequence, Mapping, Iterable, Container
from typing import Optional, Protocol, Literal, Callable

from ..cells import text
from ..cells.text import Phrase, Redirect, Words, Unit, Image
from ..cells.types import Area, Glyph, Pixels, Device, Line as LineStyle

class Core(comethod.object):
	"""
	# Core element type.

	# Common base class for all instructable application elements.
	"""

@tools.struct()
class Prompting(object):
	"""
	# Defaults controlling the behavior of command prompts.
	"""

	from dataclasses import _replace

	pg_process_identity: object
	pg_line_allocation: int
	pg_syntax_type: str
	pg_execution_types: Container[str]
	pg_limit: int

class Mode(object):
	"""
	# A mapping of user events to application instructions.

	# [ Elements ]
	# /default/
		# The default action to translate events into.
	# /mapping/
		# The Application Event to User Event index.
	# /reverse/
		# The User Event to Application Event index.
	"""

	def __init__(self, default=None):
		self.default = default
		self.mapping = dict()
		self.reverse = dict()

	def assign(self, keybind, category, action, parameters = ()):
		"""
		# Assign the character sequence to action.
		"""

		ikey = (category, action, parameters)
		if ikey not in self.mapping:
			self.mapping[ikey] = set()

		self.mapping[ikey].add(keybind)
		self.reverse[keybind] = ikey

	def event(self, kb):
		"""
		# Return the action associated with the given key.
		"""

		return self.reverse.get(kb, self.default)

# XXX: Adjust Selection and Mode to support intercepts for temporary bindings.
# The binding for return is overloaded and to eliminate
# the internal switching(routing to Refraction.activate), a trap needs to be
# employed so that open/save activation may be performed when the location bar is active.
# `Session.input.intercept(mode, ReturnKey, location.open|location.save)` where open, save and
# cancel clears the intercept.
class Selection(object):
	"""
	# A mapping of &Mode instances controlling the current application event translation mode.

	# [ Elements ]
	# /index/
		# The collection of &Mode instances assigned to their identifier.
	# /current/
		# The &Mode in &index that is currently selected.
	# /last/
		# The previous &Mode identifier.
	"""

	@property
	def mapping(self):
		"""
		# Get the currently selected mapping by the defined name.
		"""

		return self.current[0]

	@classmethod
	def standard(Class):
		return Class(standard)

	def __init__(self, index):
		self.index = index
		self.current = None
		self.last = None
		self.data = None

	def reset(self, mode):
		self.set(mode)
		self.last = self.current
		self.qualification = None

	def revert(self):
		"""
		# Swap the selected mode to &last.
		"""

		self.current, self.last = self.last, self.current

	def set(self, name):
		self.last = self.current
		self.current = (name, self.index[name])
		return self.current

	def mode(self, name):
		"""
		# Whether the given mode, &name, is currently active.
		"""
		return self.current[0] == name

	def event(self, key):
		"""
		# Look up the event using the currently selected mapping.
		"""

		return (self.current[0], self.current[1].event(key))

	def interpret(self, event):
		"""
		# Route the event to the target given the current processing state.
		"""

		mapping, operation = self.event(event)
		if operation is None:
			return (None, ('meta', 'ineffective', ()))

		return (mapping, operation)

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
	from ..configuration import symbols
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

		# [ Parameters ]
		# /verticals/
			# Tuples designating the division count and allocation width.
		"""

		height = self.fm_context.lines - (self.fm_border_width * 2)
		width = self.fm_context.span - (self.fm_border_width * 2)
		nverticals = len(verticals)
		maxverticals = max(width // allocation, 1)

		# Fill the available space; excess goes to &inheritor.
		ralloc = width // maxverticals
		for i, va in enumerate(verticals):
			if va[1] == 0:
				# Override the vertical that receives the remaining space.
				inheritor = i
				break
		else:
			inheritor = nverticals - 1
		verticals[inheritor] = (verticals[inheritor][0], 0)

		self.fm_layout = verticals
		self.fm_verticals = [
			(
				(None, 0 + self.fm_border_width),
				(allocation * x[1] + (max(x[1]-1, 0) * self.fm_border_width), height),
			)
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
		lpositions = zip(R('left'), R(loffset), v_context, rev(vertical), rev(itypes))

		# Right
		roffset = h_offset + borderx + h_limit
		rpositions = zip(R('right'), R(roffset), v_context, vertical, itypes)

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
		yield ('system-delimiter', '://')

		if self.sys_credentials:
			yield ('system-credentials', self.sys_credentials)
			if self.sys_authorization:
				yield ('system-delimiter', ':')
				yield ('system-authorization', self.sys_authorization)
			yield ('system-delimiter', '@')

		yield ('system-identity', self.sys_identity)

		if self.sys_title:
			yield ('system-delimiter', '[')
			yield ('system-title', self.sys_title)
			yield ('system-delimiter', ']')

		if path is None:
			return

		if path[:1] == '/':
			yield ('system-delimiter', '/')
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

	@classmethod
	def structure(Class, si:str, *, ri_load=ri.parse):
		"""
		# Construct a &System instance using the string representation, &si.

		# While this parses &si as a resource indicator, the query portion is
		# discarded and the path is returned as a sequence parallel to the
		# &System instance.
		"""

		parts = ri_load(si)

		return Class(
			parts['scheme'] or '',
			parts.get('user', ''),
			parts.get('password', ''),
			parts.get('host', ''),
			parts.get('address', ''),
		), parts.get('path')

@tools.struct()
class Reference(object):
	"""
	# Resource identification and information.

	# [ Elements ]
	# /ref_system/
		# The system context that should be used to interface with the resource.
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

	def replace(self, string):
		"""
		# Reconstruct the line with the given &string as the content.
		"""

		return self.__class__(
			self.ln_offset,
			self.ln_level,
			string,
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
	def lf_empty_phrase(self) -> Phrase:
		"""
		# An empty Phrase configured with &lf_theme.
		"""

		return Phrase([
			Words((0, "", self.lf_theme['empty']))
		])

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
				0x09: Redirect((2, '  ', Glyph(codepoint=ord(' ')), "\x09")),
				0x1f: Redirect((1, '\u2038',
					Glyph(codepoint=ord('-'), textcolor=0x444444),
					"\x1f"
				)),
				# Field separation escape.
				0x0010fa01: Redirect((1, '\u2423',
					Glyph(codepoint=ord(' '), textcolor=0xd9d111),
					"\U0010fa01"
				)),
			},
			obstruction=Glyph(codepoint=-1, textcolor=0x5050DF),
			representation=Glyph(codepoint=-1, textcolor=0x777777),
		):
		"""
		# Construct representations for control characters.
		"""

		for i in phrasewords:
			if len(i.text) == 1 and not isinstance(i, Redirect):
				o = ord(i.text)

				if o in constants:
					yield constants[o]
					continue

				if o < 32 and isinstance(i, Unit):
					d = hex(o)[2:].rjust(2, '0')
					yield Redirect((1, '[', obstruction, ''))
					yield Redirect((len(d), d, representation, i.text))
					yield Redirect((1, ']', obstruction, ''))
					continue
			yield i

	def segment_fields(self, fields):
		"""
		# Construct a subphrase from the given fields using &lf_theme and &lf_units.
		"""

		tg = self.lf_theme.get
		lfu = self.lf_units
		return Phrase.segment(
			(tg(ft, ft), lfu(fc))
			for ft, fc in fields
		)

	def cursor(self, line, fields) -> Iterable[Words]:
		"""
		# Construct a Phrase instance representing the structured line
		# for display with a cursor.
		"""

		if line.ln_content:
			itype = 'indentation'
		else:
			itype = 'indentation-only'

		tg = self.lf_theme.get
		content = Phrase.redirect(self.lf_units, ((tg(ft, ft), fc) for ft, fc in fields))

		yield from self.redirect_indentation(itype, line.ln_level)
		yield from self.redirect_exceptions(content)
		yield Redirect((1, ' ', tg('line-termination'), '\n'))

	def compose(self, line, fields) -> Iterable[Words]:
		"""
		# Construct a Phrase instance representing the structured line.
		"""

		if line.ln_content:
			itype = 'indentation'
		else:
			itype = 'indentation-only'

		fields = list(fields)
		if fields:
			# Strip trailing whitespace for &redirect_trail.
			fields[-1] = (
				fields[-1][0],
				fields[-1][1].rstrip()
			)

		tg = self.lf_theme.get
		content = Phrase.redirect(self.lf_units, ((tg(ft, ft), fc) for ft, fc in fields))

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

@tools.struct(weakref_slot=True)
class Cursor(object):
	"""
	# &Position pair with motion callbacks.
	"""

	lines: Position
	codepoints: Position

	@classmethod
	def allocate(Class, lo, cstart, co, cstop):
		i = Class(Position(), Position())
		i.lines.restore((lo, lo, lo+1))
		i.codepoints.restore((cstart, co, cstop))
		return i

	def coordinates(self) -> tuple[int,int]:
		"""
		# Construct the line offset, codepoint offset pairs.
		"""

		return (self.lines.get(), self.codepoints.get())

	def line_delta(self, ln_offset, deleted, inserted):
		"""
		# Update the line cursor and view area.
		"""

		cursor = self.lines

		if deleted:
			self.lines.delete(ln_offset, deleted)
		if inserted:
			self.lines.insert(ln_offset, inserted)

	def codepoint_delta(self, ln_offset, cp_offset, deleted, inserted):
		"""
		# Update the codepoint cursor.
		"""

		lo = self.lines.get()
		if lo == ln_offset:
			cp_offset -= (4) # Constant offset for internal header.
			if deleted:
				self.codepoints.delete(cp_offset, deleted)
			if inserted:
				self.codepoints.insert(cp_offset, inserted)

@tools.struct()
class Expression(object):
	"""
	# Common base class for ivectors elements.

	# Holds common parsing functions for transforming syntax fields
	# into &Redirection, &Instruction, &Procedure, and &Composition.
	"""

	_ec_chars = ' \n\r"#\\|&><^*'
	_ec_interpret = str.maketrans(
		''.join(chr(0x10fa00 + x) for x in range(1, len(_ec_chars)+1)),
		_ec_chars,
	)
	_ec_protect = str.maketrans(
		_ec_chars,
		''.join(chr(0x10fa00 + x) for x in range(1, len(_ec_chars)+1)),
	)
	_decode_escapes = (lambda x: x.translate(Expression._ec_interpret))
	_encode_escapes = (lambda x: x.translate(Expression._ec_protect))

	@classmethod
	def join_field(Class, parts):
		"""
		# Compose the parts into a formatted string.

		# Translate escapes and combine literals.
		"""

		field = ''

		i = 0
		redirect = port = None
		for ft, fv in parts[:2]:
			if ft == 'inclusion-operation' and fv[:1] != '-':
				# All operations are redirects, except those with a leading dash.
				i += 1
				redirect = fv
				break
			elif ft != 'inclusion-words':
				# Optional leading file descriptor number.
				port = fv
			i += 1
		else:
			# Not a redirect.
			i = 0

		lit = None
		for ft, fs in parts[i:]:
			if ft.startswith('inclusion-'):
				field += Class._decode_escapes(fs)
			elif lit is not None:
				if ft == 'literal-stop':
					lit += fs[:-1]
					field += lit
					lit = None
				elif ft != 'literal-start':
					lit += fs
				else:
					lit += fs
			elif ft == 'literal-start':
				lit = fs[1:]
			else:
				# Exclusion
				pass
		else:
			if lit:
				# Open literal.
				field += lit

		if redirect is not None:
			out = (redirect, port, field)
		else:
			out = field
		return out

	@classmethod
	def identify_edges(Class, syntax):
		"""
		# Find the first and last non-space and non-exclusion fields.

		# Groups syntax fields for instruction field formatting.
		"""

		i = -1
		typ = 'inclusion-space'
		fv = ''

		while typ == 'inclusion-space' or typ.startswith('exclusion-'):
			i += 1
			try:
				typ, fv = syntax[i]
			except IndexError:
				return None
		start = i

		i = 0
		typ = 'inclusion-space'
		fv = ''
		while typ == 'inclusion-space' or typ.startswith('exclusion-'):
			i -= 1
			typ, fv = syntax[i]

		stop = len(syntax) + i + 1
		return slice(start, stop)

	@classmethod
	def join_lines(Class, lines):
		"""
		# Process the fields in &lines to recognize the procedure boundaries.
		"""

		ilines = iter(lines)
		try:
			last = next(ilines)

			# Find the first non-empty line.
			ledge = Class.identify_edges(last)
			while ledge is None:
				last = next(ilines)
				ledge = Class.identify_edges(last)
		except StopIteration:
			# Empty lines.
			return

		cwp = last[ledge]

		for current in ilines:
			cedge = Class.identify_edges(current)
			if cedge is None:
				# Nothing to add.
				continue

			if current[cedge.start][0] == 'inclusion-terminator':
				cwp.extend(current[cedge])
			elif last[ledge.stop-1][0] == 'inclusion-terminator':
				cwp.extend(current[cedge])
			else:
				yield cwp
				cwp = current[cedge]

			ledge = cedge
			last = current

		if cwp:
			yield cwp

	@classmethod
	def terminate(Class, syntax):
		"""
		# Scan the syntax fields for instruction vector terminators and
		# isolate the joined vector fields by associating them with their
		# following terminator.
		"""

		parts = []
		fields = []
		termination = None

		for fp in syntax:
			ft, fv = fp

			if ft == 'inclusion-space':
				assert set(fv) == {' '}
				# End of field.
				pass
			elif ft == 'inclusion-terminator':
				termination = fv
			else:
				# Add for subsequent interpretation.
				parts.append(fp)
				continue

			if parts:
				fields.append(Class.join_field(parts))
				parts = []

			if termination is not None:
				if termination == '\\':
					# Carry fields.
					continue

				yield (termination, fields)
				termination = None
				fields = []
		else:
			if parts:
				fields.append(Class.join_field(parts))
			if fields:
				yield ('', fields)

@tools.struct()
class Redirection(Expression):
	"""
	# A redirect operator of an instruction.

	# The structure defining the parts of a redirection.
	"""

	operator: str
	port: int|None
	operand: str

	def suffix(self, string):
		"""
		# Reconstruct with &string suffixed on &operand.
		"""

		return self.__class__(self.operator, self.port, self.operand+string)

	def default_port(self) -> int:
		"""
		# Identify the default port from the &operator.
		"""

		if '<<' in self.operator:
			# Source.
			return 3
		elif self.operator == '.<':
			raise ValueError("working directory change")
		elif '<' in self.operator:
			return 0
		elif '>' in self.operator:
			return 1
		elif '^' in self.operator:
			# Normally special cased with split.
			return -1

	def split(self, iport=0, oport=1):
		"""
		# Deconstruct the combination, `^`, into a pair of input and output
		# &Redirection instances to eliminate the need for processing
		# combinations further downstream.
		"""

		assert self.operator[:1] == '^'

		if self.operator[:2] == '^>':
			suffix = self.operator[2:]
			out = '>>'
		else:
			suffix = self.operator[1:]
			out = '>'

		return (
			Redirection('<'+suffix, iport, self.operand),
			Redirection(out+suffix, oport, self.operand),
		)

@tools.struct()
class Instruction(Expression):
	"""
	# Expression structure for application instructions and system commands.
	"""

	fields: Sequence[str]
	redirects: Sequence[Redirection]

	def sole(self, *types):
		return None

	def title(self) -> str:
		"""
		# The first field of the instruction.
		"""

		if self.fields:
			return self.fields[0]
		else:
			return "[-]"

	def empty(self) -> bool:
		"""
		# Whether the instruction is specified, `len(.fields) == 0`.
		"""

		return not self.fields

	def invokes(self, name:str) -> bool:
		"""
		# Whether &name is consistent with the first field of the instruction.
		"""

		return self.fields[0] == name if self.fields else False

	@classmethod
	def isolate(Class, fields):
		"""
		# Construct an instance isolating the fields into their respective level.
		# Sorts redirects from instruction vector fields.
		"""

		fs = []
		rs = []
		exts = {}

		for f in fields:
			if f.__class__ is str:
				fs.append(f)
			else:
				p = None if f[1] is None else int(f[1]) # Redirect port.
				r = Redirection(f[0], p, f[-1])
				if f[0] == '<<':
					# Other redirects overwrite the port.
					# Text extends previous text redirects.
					if p in exts:
						ri = exts[p]
						rs[ri] = rs[ri].suffix(f[-1])
					else:
						exts[p] = len(rs)
						rs.append(r)
				else:
					rs.append(r)

		return Class(fs, rs)

	def split_redirects(self):
		"""
		# Isolate standard input and output redirections and reconstruct
		# the &Instruction with the remainder.

		# Needed for integrating redirects into &Composition's.

		# [ Returns ]
		# Triple containing the reconstructed &Instruction, the sequence
		# of &Redirection to be integrated into the beginning of the
		# composition, and the sequence to be integrated into the end of
		# the composition.
		"""

		head = []
		tail = []
		remains = []
		for r in self.redirects:
			p = r.port
			if p is None:
				p = r.default_port()

			if r.operator[:1] == '^':
				# Handle combination cases by splitting them.
				assert p is None
				ri, ro = r.split()
				head.append(ri)
				tail.append(ro)
			if p == 0 and r.operator[:1] == '<':
				# Standard input redirection.
				head.append(r)
			elif p == 1 and r.operator[:1] == '>':
				# Standard output redirection.
				tail.append(r)
			else:
				remains.append(r)

		return self.__class__(self.fields, remains), head, tail

	def redirect(self, work, system, path):
		"""
		# Allocate the file descriptor mappings for an invocation.
		"""

		for r in self.redirects:
			if r.operator[:1] == '^':
				rin, rout = r.split()
				yield (system.redirect(work, rin, path), rin.port)
				yield (system.redirect(work, rout, path), rout.port)
			else:
				p = r.port
				if p is None:
					p = r.default_port()
				yield (system.redirect(work, r, path), p)

@tools.struct()
class Composite(Expression):
	"""
	# Superclass of all expressions consisting of multiple instructions.
	"""

	@classmethod
	def compose(Class, integration, tail, exclusion=False):
		# Reduce as much as possible.
		while ii := integration.sole(Composite, Instruction):
			integration = ii
		while ii := tail.sole(Composite, Instruction):
			tail = ii

		if isinstance(tail, Composition):
			c = tail
			if exclusion:
				del c.parts[0:1]
			c.parts.insert(0, integration)
		else:
			if isinstance(tail, Procedure) and isinstance(tail.steps[0], Composition):
				if exclusion:
					del tail.steps[0].parts[0:1]

				# Not sole and opens with a composition.
				if isinstance(integration, Procedure):
					tail.steps[0].parts.insert(0, integration)
					return tail
				else:
					if tail.conditions[0] == 'always':
						rc = tail.steps[0]
						integration.parts.extend(rc.parts)
						del tail.steps[0:1]
				tails = [tail]
			elif exclusion:
				# tail is not a composition or procedure
				tails = []
			else:
				tails = [tail]
			c = Composition([integration] + tails)

		return Procedure([c], ['always'])

	@classmethod
	def structure(Class, iterminated):
		ctypes = {
			'': 'always',
			'&': 'always',
			'&*': 'always',
			'&+': 'completed',
			'&-': 'failed',
			'&#': 'never',
		}
		group = []
		conditions = []
		continued = []

		for t, ifields in iterminated:
			i = Instruction.isolate(ifields)

			if t not in {'|', '||', '|#', '||#'}:
				# Regular instruction step.
				conditions.append(ctypes[t])
				group.append(i)
			else:
				# Procedure leading a composition.
				if t in {'||', '||#'}:
					# Handle precedence switch.
					group.append(i)
					conditions.append('always')
					lead = Procedure(group, conditions)
					group = []
					conditions = []
					tail = Class.structure(iterminated)
					return Class.compose(lead, tail, exclusion=(t=='||#'))

				# Redirect only instruction.
				if isinstance(i, Instruction) and i.empty() and i.redirects:
					i, fhead, ftail = i.split_redirects()
					c = []
				else:
					c = [i]
					i = None
					fhead = ftail = []

				skip = (t == '|#')
				for ct, ci in iterminated:
					if skip:
						skip = False
					else:
						c.append(Instruction.isolate(ci))

					if ct != '|':
						if ct in {'||', '||#'}:
							# Handle precedence switch.
							exclusion = (ct == '||#')
							tail = Class.structure(iterminated)

							if tailc := tail.sole(Composition):
								if exclusion:
									del tailc.parts[0:1]
								c.extend(tailc.parts)
							elif taili := tail.sole(Instruction):
								if not exclusion:
									c.append(taili)
							elif itail := tail.sole(Procedure):
								if itail.sole(Composition):
									if exclusion:
										del itail.steps[0].parts[0:1]
									c.extend(itail.steps[0])
								elif not exclusion:
									c.append(tail.steps[0])
							else:
								# Procedure.
								if not exclusion:
									c.append(tail)
						elif ct == '|#':
							skip = True
						else:
							conditions.append(ctypes[ct])
							break
				else:
					# End of instructions during composition.
					# Unnatural as the empty type is usually the final terminator.
					conditions.append('always')

				# Distribute the split redirects from a leading empty instruction.
				if fhead:
					c[0].redirects.extend(fhead)
				if ftail:
					c[-1].redirects.extend(ftail)

				if len(c) < 2:
					# Redirect only instructions filtered.
					i = c[0]
				else:
					i = Composition(c)
				group.append(i)

		p = Procedure(group, conditions)
		if p.steps:
			if sub := p.sole(Procedure):
				return sub
		return p

@tools.struct()
class Composition(Composite):
	"""
	# A series of instructions providing the input for the following.
	"""

	parts: Sequence[Instruction|Composite]

	def sole(self, *types):
		if len(self.parts) > 1:
			return None
		if isinstance(self.parts[0], types):
			return self.parts[0]
		return None

	def title(self) -> str:
		"""
		# The first and last title.
		"""

		return '->'.join((self.parts[0].title(), self.parts[-1].title()))

@tools.struct()
class Procedure(Composite):
	"""
	# A series of instructions to be executed sequentially.

	# [ Elements ]
	# /steps/
		# The sequence of instructions, compositions, or procedures.
	# /conditions/
		# The conditions under which a corresponding commands may be executed.
	"""

	steps: Sequence[Instruction|Composite]
	conditions: Sequence[str|None]

	def title(self) -> str:
		"""
		# The titles of each instruction.
		"""

		return '+'.join(x.title() for x in self.steps)

	def empty(self):
		return len(self.steps) == 0

	def sole(self, *types):
		if len(self.steps) > 1:
			return None
		if isinstance(self.steps[0], types):
			return self.steps[0]
		return None

	def iterate(self):
		return zip(self.steps, map(self.checks.__getitem__, self.conditions))

	checks = {
		'never': (lambda x: True),
		'always': (lambda x: False),
		'completed': (0).__ne__,
		'failed': (0).__eq__,
	}

@tools.struct(weakref_slot=True)
class Work(object):
	"""
	# Procedure dispatch context tracking process status.
	"""

	target: object
	source: Sequence[Line]
	procedures: Sequence[Procedure]
	cursors: Sequence[object]
	status: Mapping[object, dict]

	@classmethod
	def allocate(Class, relation, lines):
		return Class(weakref.proxy(relation), lines, [], [], {})

	@property
	def system(self):
		"""
		# System expressed in the first line of &source.
		"""

		return System.structure(self.source[0].ln_content)

	def spawn(self, system, path, proc, fdmap=()) -> int:
		"""
		# Add &proc to the sequence of procedures, allocate
		# a cursor, and dispatch its first step.

		# [ Returns ]
		# The index of the procedure.
		"""

		# The copy must be made here as the pipe will close
		# the local file descriptors soon after.
		copy = system.replicate(fdmap)

		index = len(self.cursors)
		cursor = system.evaluate(weakref.proxy(self), index, path, proc, copy)
		self.procedures.append(proc)
		self.cursors.append(cursor)
		self.proceed(index, None, None)

		return index

	def prepare(self, system, path, proc):
		"""
		# Extend the set of dispatched procedures.
		"""

		return tools.partial(self.spawn, system, path, proc), path, ()

	def proceed(self, index, pid, code):
		"""
		# Proceed to the next step and configure the next callback.
		"""

		try:
			if pid in self.status or pid is None:
				self.status[pid] = code
				xl = self.cursors[index].send(code)
				self.status[xl.event.source] = xl
		except StopIteration:
			# End of procedure.
			self.cursors[index] = None
			if self.cursors.count(None) == len(self.cursors):
				self.target.annotate(None)

	from os import kill
	def interrupt(self):
		# File descriptors can be held by the cursors,
		# so force close the generators here.
		for c in self.cursors:
			if c is not None:
				c.close()

		# Let the later completions finish the status and zero cursors.
		for pid, link in self.status.items():
			if link is not None and not isinstance(link, int):
				try:
					self.kill(pid, 9)
				except ProcessLookupError:
					pass

@dataclass()
class Syntax(object):
	"""
	# Syntax context for prompt and location formatting.

	# Both views make heavy use of system contexts.

	# [ Elements ]
	# /source/
		# A self pointer to the resource being formatted by this instance.
		# This avoids a reference cycle by only being present on the
		# the view's &Reformulations, not the source's.
	# /executions/
		# The work context elements for reference. Allows for filesystem
		# queries and command indexes to be referenced.
	"""

	source: object = None
	executions: object = None
	ivectors: object = None
	iv_isolate: object = None

	_field_sets = {}
	_type_map = {
		'host': 'system-identity',
		'user': 'system-credentials',
		'password': 'system-authorization',
		'path': 'system-path',
		'scheme': 'system-method',
		'address': 'system-title',
		'port': 'system-invalid-field',
		'fragment': 'system-invalid-field',

		'delimiter': 'system-delimiter',
		'type': 'system-delimiter',
		'delimiter-path-only': 'system-delimiter',
		'delimiter-path-segments': 'system-delimiter',
		'delimiter-path-final': 'system-delimiter',
		'delimiter-path-initial': 'system-delimiter',

		'path-segment': 'system-path',
		'resource': 'system-path',
	}

	_prompt_commands = {
		'cd',
	}

	@classmethod
	def interpret_field_text(Class, parts):
		"""
		# Compose the parts into a formatted string.

		# Translate escapes and combine literals.
		"""

		out = ''
		lit = None

		for ft, fs in parts:
			if ft.startswith('inclusion-'):
				out += Expression._decode_escapes(fs)
			elif lit is not None:
				if ft == 'literal-stop':
					lit += fs[:-1]
					out += lit
					lit = None
				elif ft != 'literal-start':
					lit += fs
				else:
					lit += fs
			elif ft == 'literal-start':
				lit = fs[1:]
			else:
				# Exclusion
				pass
		else:
			if lit:
				# Open literal.
				out += lit

		return out

	def classify_command(self, command:str, *, invalid='invalid-command'):
		"""
		# Identify the type of the command.
		"""

		if command in self._prompt_commands:
			return 'prompt-control'

		sys, path = System.structure(self.source.sole(0).ln_content)
		if sys in self.executions:
			exe = self.executions[sys]
			if command in exe.index:
				return exe.command_type
		else:
			# No system.
			return invalid

		try:
			pwd = exe.fs_root + path
		except AttributeError:
			pass
		else:
			try:
				if (pwd @ command).fs_status().executable:
					return exe.command_type
			except (OSError, ValueError):
				pass

		return invalid

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
					for l in current.fs_follow_links():
						yield ('path-link', f)
						break
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

	def system_context(self, lo=0):
		"""
		# Identify the system context from the first line of the source.

		# [ Returns ]
		# The &System, &.system.WorkContext, and the context's path as a sequence.
		"""

		try:
			li = self.source.sole(lo)
			sri = li.ln_content
		except IndexError:
			sri = ''

		sys, path = System.structure(sri)

		if sys in self.executions:
			exe = self.executions[sys]
			sys = exe.identity
		else:
			exe = None

		return (sys, exe, path)

	def location_path(self):
		"""
		# Get the current location path.
		"""

		sys, exe, path = self.system_context()
		path = exe.fs_root + path

		for li in self.source.select(1, self.source.ln_count()):
			path @= li.ln_content

		return exe, path

	def isolate_rl_path(self, ln, *, separator='/', relative=None):
		"""
		# Structure the path components of &line relative to &rpath.
		# If &line begins with a root directory, it is interpreted absolutely.
		"""

		s = separator
		lc = ln.ln_content
		if not lc:
			return ()

		sys, exe, path = self.system_context()

		if ln.ln_offset == 0:
			sysparts, path = self.structure_locator(ln.ln_content)
			ctxfields = list(sysparts)

			sys, path = System.structure(ln.ln_content)
			if path is not None:
				ctxfields.append(('filesystem-root', '/'))
				if path:
					ctxfields.extend(self.typed_path_fields(exe.fs_root, path, separator=s))

			return ctxfields

		if exe is None:
			return [('error-condition', lc)]

		if relative or not lc.startswith(s):
			# pathref defaults to pwd, but is overwritten to fetch initial
			# line of the location's resource.
			return self.typed_path_fields(exe.fs_root + path, lc.split(s), separator=s)
		else:
			return self.typed_path_fields(exe.fs_root, lc.split(s), separator=s)

	def update_field_sets(self):
		self._field_sets['system-delimiter'] = {'://', '/', '@', ':', '[', ']'}
		self._field_sets['system-title'] = {''}
		self._field_sets['system-authorization'] = {''}
		ignored = {'system-path'}

		for sys in self.executions:
			for typ, v in sys.i_format():
				if typ in ignored:
					continue

				if typ not in self._field_sets:
					self._field_sets[typ] = set()

				self._field_sets[typ].add(v)

	def valid_system_field(self, ftype, v):
		if not self._field_sets:
			self.update_field_sets()

		if ftype not in self._field_sets:
			# Not checked. (paths)
			return True

		if v in self._field_sets[ftype]:
			return True

		return False

	def system_locator_fields(self, parts):
		for typ, v in ri.tokens(parts):
			stype = self._type_map[typ]

			if self.valid_system_field(stype, v):
				yield (stype, v)
			else:
				yield ('system-invalid-field', v)

	def structure_locator(self, string):
		parts = ri.parse(string)
		paths = parts.pop('path', None)
		return self.system_locator_fields(parts), paths

	skip_types = {
		'literal-space',
		'inclusion-space',

		'inclusion-stop-exclusion',
		'exclusion-start',
		'exclusion-stop',
		'exclusion-delimit',
		'exclusion-space',
		'exclusion-words',
		'exclusion-fragment',
	}
	_redirects = {
		'>', '<', '>>',
		'<=', '>=', '>>=',
	}

	def isolate_instructions(self, fi):
		"""
		# Scan the iterator for the first identifier and validate its
		# index presence or filesystem location.
		"""

		cmdparts = []
		continued = True

		while continued:
			continued = False

			for tf in fi:
				# Skip leading spaces.
				if tf[0] in self.skip_types:
					yield tf
					continue

				if tf == ('inclusion-operation', '\\'):
					# Arguments until terminator.
					yield tf
					return
				elif tf[0] == 'inclusion-terminator':
					# Empty command? Continue seeking.
					yield ('command-terminator', tf[1])
					continue

				# Hold start of command.
				cmdparts.append(tf)
				break

			tail = None
			for tf in fi:
				if tf[0] in {'inclusion-space', 'inclusion-terminator'}:
					# End of field with space or terminator.
					tail = tf
					break
				elif tf[0] == 'inclusion-operation' and tf[1] in self._redirects:
					# End of field with, likely, redirect.
					tail = tf
					break
				else:
					# Part of the command.
					cmdparts.append(tf)

			# Get the text of the command for validation.
			command = self.interpret_field_text(cmdparts)
			ctype = self.classify_command(command)
			for ft, fs in cmdparts:
				if not ft.startswith('exclusion-') and ft not in {'literal-start', 'literal-stop'}:
					# Classify parts that are not comments or literal boundaries.
					yield (ctype, fs)
				else:
					# Primarily for revealing comments.
					yield (ft, fs)

			if tail is not None:
				# Last field
				if tail[0] == 'inclusion-terminator':
					continued = True
					yield ('command-terminator', tail[1])
				else:
					yield tail
				tail = None
			cmdparts = []

	def isolate_prompt_fields(self, ln):
		"""
		# Identify the field types of the prompt lines.
		"""

		if ln.ln_offset == 0:
			sysfields, syspath = self.structure_locator(ln.ln_content)
			yield from sysfields

			sys, path = System.structure(ln.ln_content)
			try:
				sysroot = self.executions[sys].fs_root
			except (AttributeError, KeyError, TypeError):
				if path is not None:
					for p in path:
						yield ('system-path', '/')
						yield ('system-path', p)
			else:
				if path is not None:
					if path:
						yield ('system-path', '/')
						yield from self.typed_path_fields(sysroot, syspath)
					else:
						yield ('system-path', '/')

			return

		fi = iter(self.iv_isolate(self.ivectors, ln))

		yield from self.isolate_instructions(fi)

		for tf in fi:
			if tf[0] == 'inclusion-terminator':
				yield ('command-terminator', tf[1])
				yield from self.isolate_instructions(fi)
			else:
				yield tf
