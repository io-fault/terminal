"""
# Supporting structures and types required by &.elements.
"""
import itertools
import collections
from typing import Optional, Protocol

from dataclasses import dataclass
from fault.context import tools

from collections.abc import Sequence, Mapping

from ..cells import text
from ..cells.types import Area, Cell, Device

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

	ref_icons: Mapping[str, text.Phrase]|None

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

@dataclass(match_args=False, eq=False)
class View(object):
	"""
	# A displayed view of a &Refraction.

	# [ Elements ]
	# /area/
		# The bounding rectangle that the &image is drawn within.
	# /image/
		# Phrase sequence to be rendered to the &area of the screen.
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
	Empty = text.Phrase([
		text.Words((0, "", text.Cell(codepoint=-1, cellcolor=0x000000)))
	])

	area: Area
	image: Sequence[text.Phrase]
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

	@property
	def height(self):
		return self.area.lines
	@property
	def width(self):
		return self.area.span

	def trim(self):
		"""
		# Limit the image to the display's height.
		"""

		d = self.area.lines
		del self.image[d:]
		del self.whence[d:]

		assert len(self.image) == self.height
		assert len(self.whence) == self.height

	def compensate(self):
		"""
		# Extend the image with &Empty lines until the display is filled.
		"""

		# Pad end with empty lines.
		start = len(self.image)
		d = self.height - start
		self.image.extend([self.Empty] * d)
		self.whence.extend([((0, 0), 0)] * d)

		assert len(self.image) == self.height
		assert len(self.whence) == self.height
		yield from self.render(slice(start, len(self.image)))

	def rendercells(self, offset, cells):
		"""
		# Sequence the necessary display instructions for rendering
		# a single, View relative, line at &offset.
		"""

		ec = text.Cell(codepoint=-1, cellcolor=0x000000)
		AType = self.area.__class__
		rx = self.area.x_offset
		ry = self.area.y_offset
		width = self.area.span
		cview = list(cells)
		ccount = len(cview)
		hoffset = self.horizontal_offset
		voffset = offset

		# Erase to margin.
		v = (width - (ccount - hoffset))
		if v > 0:
			cview.extend(ec for i in range(v))
		else:
			cview = cview[hoffset:hoffset+width]

		return AType(offset + ry, 0 + rx, 1, width), cview

	def render(self, area, *, min=min, max=max, len=len, list=list, zip=zip):
		"""
		# Sequence the necessary display instructions for rendering
		# the &area reflecting the current &image state.
		"""

		ec = text.Cell(codepoint=-1, cellcolor=0x000000)
		AType = self.area.__class__
		rx = self.area.x_offset
		ry = self.area.y_offset
		limit = self.area.span
		voffset = area.start or 0 # Context seek offset.
		hoffset = self.horizontal_offset

		cv = []
		for (phrase, w) in zip(self.image[area], self.whence[area]):
			cells = list(phrase.render())
			visible = min(limit, max(0, len(cells) - hoffset))
			v = limit - visible

			cv.extend(cells[hoffset:hoffset+visible])
			if v > 0:
				cv.extend(ec for i in range(v))
			else:
				assert visible == limit
			voffset += 1
		yield AType(ry + area.start, rx, (voffset - (area.start or 0)), limit), cv

	def refresh(self):
		"""
		# Emit display instructions for redrawing the view's entire image.
		"""

		yield from self.render(slice(0, None))
		yield from self.compensate()

	def vertical(self, rf):
		v = rf.visible[0]
		return slice(v, v+self.height, 1)

	def horizontal(self, rf):
		h = rf.visible[1]
		return slice(h, h+self.width, 1)

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
	"""

	# Indicator images (characters) and colors.
	from . import symbols, palette
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
	fm_icolors = palette.range_colors

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
		self.fm_context = None
		self.fm_header_size = header
		self.fm_footer_size = footer
		self.fm_border_width = border
		self.fm_verticals = []
		self.fm_divisions = collections.defaultdict(list)
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
						elif ds[1] and ry >= dd[1] + ds[1]:
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

	def redistribute(self, allocation=90):
		"""
		# Distribute the available vertical area so that each page has at least the
		# given &width.
		"""

		height = self.fm_context.lines - (self.fm_border_width * 2)
		width = self.fm_context.span - (self.fm_border_width * 2)
		count = max(width // allocation, 1)
		ralloc = width // count # remainder goes to last pane

		offset = ralloc + self.fm_border_width # include initial for addressing.
		self.fm_verticals = [
			((x + 1, 0 + self.fm_border_width), (ralloc, height))
			for x in map(offset.__mul__, range(count))
		]

		# Reconstruct last record with updated width.
		lwidth = width - (offset * (count-1))
		lp, ld = self.fm_verticals[-1]
		self.fm_verticals[-1] = (lp, (lwidth, ld[1]))
		for i, p in enumerate(self.fm_verticals):
			if i not in self.fm_divisions:
				self.fm_divisions[i] = [p + ((2, 0),)]
			self.update_inner_intersections(i)

		return len(self.fm_verticals)

	def divide(self, page, divisions):
		"""
		# Split the page (vertical) into divisions
		"""

		pp, pd = self.fm_verticals[page]
		self.fm_divisions[page] = [
			((pp[0], p), (pd[0], height), (2, 0))
			for (p, height) in self.distribute(pd[1], (pd[1] // divisions)-1)
		]
		self.update_inner_intersections(page)

	def configure(self, area, divisions):
		"""
		# Configure the frame to have `len(divisions)` verticals where
		# each element describes the number of divisions within the vertical.
		"""

		self.fm_context = area
		alloc = max(0, (self.fm_context.span // len(divisions)) - 1)
		self.redistribute(alloc)
		for i, vd in enumerate(divisions):
			self.divide(i, vd)
		return self

	@property
	def configuration(self):
		"""
		# The configured area and divisions.
		"""

		return self.fm_context, tuple(map(len, self.fm_divisions.values()))

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
			dimensions = (lambda: (width-dl-dr, height-dt-db))
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
			dimensions = (lambda: (width, db-vborder))
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
						(h, v + vd[1] - footer), vd[0])

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
			ic = self.fm_icolors[itype]

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

			yield (position, ic, ii, re)
