"""
# Application frame initialization and status updates.
"""
import collections
import itertools

from fault.context.tools import struct

from . import palette
from . import symbols
from .types import Refraction

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

	def __init__(self, area, *, border=1, header=2, footer=0):
		self.fm_context = area
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

	def configure(self, *divisions):
		"""
		# Configure the frame to have `len(divisions)` verticals where
		# each element describes the number of divisions within the vertical.
		"""

		alloc = max(0, (self.fm_context.span // len(divisions)) - 1)
		self.redistribute(alloc)
		for i, vd in enumerate(divisions):
			self.divide(i, vd)
		return self

	def reconfigure(self, area):
		"""
		# Update the model with the new screen dimensions.
		"""

		self.fm_context = area
		self.configure(*map(len, self.fm_divisions.values()))

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
