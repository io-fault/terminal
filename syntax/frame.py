"""
# Application element implementations.

# # &Session
# # &Frame
# # &Refraction
"""
from collections.abc import Sequence
import collections
import itertools
import weakref

from . import palette
from . import symbols
from . import location
from . import projection
from . import cursor
from . import annotations

from ..cells.types import Cell, Area
from .types import Refraction, View, Reference

class Frame(object):
	"""
	# Frame implementation for laying out and interacting with a set of refactions.

	# [ Elements ]
	# /area/
		# The location and size of the frame on the screen.
	# /index/
		# The position of the frame in the session's frame set.
	# /title/
		# User assigned identifier for a frame.
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

	def __init__(self, theme, keyboard, area, index=None, title=None):
		self.theme = theme
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
		self.reflections = {}
		self._resets = []

	def reflect(self, ref:Reference, *sole):
		"""
		# Iterate through all the Refractions representing &ref and
		# its associated view. &sole, as an iterable, is returned if
		# no refractions are associated with &ref.
		"""

		return self.reflections.get(ref.ref_path, sole)

	def attach(self, dpath, refraction):
		"""
		# Assign the &refraction to the view associated with
		# the &division of the &vertical.

		# [ Returns ]
		# A view instance whose refresh method should be dispatched
		# to the display in order to update the screen.
		"""

		vi = self.paths[dpath]
		current = self.refractions[vi]
		self.returns[vi] = current
		view = self.views[vi]
		self.reflections[current.origin.ref_path].discard((current, view))

		self.refractions[vi] = refraction
		mirrors = self.reflections[refraction.origin.ref_path]
		mirrors.add((refraction, view))
		refraction.parallels = weakref.proxy(mirrors)

		if (self.vertical, self.division) == dpath:
			self.refocus()

		# Configure and refresh.
		refraction.configure(view.area)
		view.offset = refraction.visible[0]
		view.horizontal_offset = refraction.visible[1]
		view.version = refraction.log.snapshot()
		view.update(slice(0, None), [
			refraction.render(ln)
			for ln in refraction.elements[view.vertical(refraction)]
		])

		return view

	def chpath(self, dpath, reference, *, snapshot=(0, 0, None)):
		"""
		# Update the refraction's location.
		"""

		header = self.headings[self.paths[dpath]]

		lrender = location.type(self.theme, reference.ref_context, header.area)[-1]
		header.truncate()
		header.offset = 0
		header.version = snapshot

		header.update(slice(0, 2), list(
			map(lrender, location.determine(reference.ref_context, reference.ref_path))
		))

		return header.render(slice(0, 2))

	def chresource(self, path, refraction):
		"""
		# Change the resource associated with the &division and &vertical
		# to the one identified by &path.
		"""

		yield from self.attach(path, refraction).refresh()
		yield from self.chpath(path, refraction.origin)

	def fill(self, refractions):
		"""
		# Fill the views with the given &refractions overwriting any.
		"""

		self.refractions[:] = refractions
		self.reflections.clear()

		# Align returns size.
		n = len(self.refractions)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for ((v, d), rf, view) in zip(self.panes, self.refractions, self.views):
			rf.configure(view.area)
			self.reflections[rf.origin.ref_path].add((rf, view))

	def remodel(self, area=None, divisions=None):
		"""
		# Update the model in response to changes in the size or layout of the frame.
		"""

		da, dd = self.structure.configuration
		if area is None:
			area = da
		if divisions is None:
			divisions = dd

		self.structure.configure(area, divisions)

		self.reflections = collections.defaultdict(set)
		self.panes = list(self.structure.iterpanes())
		self.paths = {p: i for i, p in enumerate(self.panes)}

		self.views = list(
			View(Area(*ctx), [], [], {'top': 'weak'})
			for ctx in self.structure.itercontexts(area)
		)

		# Locations
		self.headings = list(
			View(Area(*ctx), [], [], {'bottom': 'weak'})
			for ctx in self.structure.itercontexts(area, section=1)
		)

	def refresh(self):
		"""
		# Refresh the view images.
		"""

		for rf, view in zip(self.refractions, self.views):
			projection.refresh(rf, view, rf.visible[0])
			view.version = rf.log.snapshot()

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
			yield from self.chpath(dpath, previous.origin)

	def render(self, screen):
		"""
		# Render a complete frame using the current view image state.
		"""

		border = Cell(textcolor=0x666666)
		def rborder(i, BCell=border, ord=ord):
			for ar, ch in i:
				a = Area(*ar)
				yield a, [BCell.inscribe(ord(ch))] * a.volume

		aw = self.area.span
		ah = self.area.lines
		yield from rborder(self.structure.r_enclose(aw, ah))
		yield from rborder(self.structure.r_divide(aw, ah))

		for p, rf, v in zip(self.panes, self.refractions, self.views):
			yield from self.chpath(p, rf.origin)
			yield from v.render(slice(0, None))

		status = list(self.indicate(self.focus, self.view))
		self._resets[:] = [(area, screen.select(area)) for area, _ in status]
		yield from status

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

	def prepare(self, session, type, dpath, *, extension=None):
		"""
		# Prepare the heading for performing a query.
		# Supports find, seek, and rewrite queries.
		"""

		from .query import refract, find, seek, rewrite
		vi = self.paths[dpath]
		ref = self.refractions[vi].origin
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		view = self.headings[vi]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		self.focus, self.view = (
			refract(session, self, view, context, state,
				{
					'search': find,
					'seek': seek,
					'rewrite': rewrite,
				}[type]
			),
			view,
		)

	def relocate(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# load the data into a session resource for editing in the view.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].origin

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(self.theme, view, ref.ref_context, ref.ref_path, location.open),
			view,
		)

		self.focus.annotation = annotations.Filesystem('open',
			self.focus.structure,
			self.focus.elements,
			*self.focus.focus
		)

	def rewrite(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# write the subject's elements to the location upon activation.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].origin

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(self.theme, view, ref.ref_context, ref.ref_path, location.save),
			view,
		)

		self.focus.annotation = annotations.Filesystem('save',
			self.focus.structure,
			self.focus.elements,
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

		self.refocus()
		if rf is self.focus:
			# Not a location or command; check annotation.
			if rf.annotation is not None:
				rf.annotation.close()
				rf.annotation = None
			return

		# Restore location.
		del rf.elements[:]
		rf.visibility[0].datum = view.offset
		rf.visibility[1].datum = view.horizontal_offset
		rf.visible[:] = (view.offset, view.horizontal_offset)
		yield from self.chpath(dpath, self.focus.origin, snapshot=rf.log.snapshot())

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

	def indicate(self, focus, view):
		"""
		# Render the (cursor) status indicators.

		# [ Parameters ]
		# /focus/
			# The &types.Refraction whose position indicators are being drawn.
		# /view/
			# The &types.View connected to the refraction.

		# [ Returns ]
		# Iterable of reset sequences that clears the cursor position.
		"""

		rx, ry = (0, 0)
		ctx = view.area
		vx, vy = (ctx.x_offset, ctx.y_offset)
		hoffset = view.horizontal_offset
		top, left = focus.visible
		hedge, edge = (ctx.span, ctx.lines)

		# Get the cursor line.
		v, h = focus.focus
		ln = focus.focus[0].get()
		try:
			line = focus.elements[ln]
		except IndexError:
			line = ""

		# Render cursor line.
		erase = 0
		rln = ln - top
		sln = vy + rln
		fai = focus.annotation
		real = None
		if rln >= 0 and rln < edge:
			# Focus line is visible.
			# Use cached version in image if available.
			whole = view.image[rln]
			w = view.whence[rln]
			if fai is not None:
				# Overwrite, but get the cell count of the un-annotated form first.
				real = whole.cellcount()
				lfields = focus.structure(line)
				fai.update(line, lfields)
				afields = list(annotations.extend(fai, lfields))
				whole = focus.format(afields)
				w = whole.seek((0, 0), hoffset, *whole.m_cell)
		else:
			# Still need translations for scale_ipositions,
			# render off screen line as well.
			fai = None
			whole = focus.render(line)
			w = whole.seek((0, 0), hoffset, *whole.m_cell)

		m_cell = whole.m_cell
		m_cp = whole.m_codepoint
		hs = h.snapshot()

		hcp = whole.tell(w[0], *m_cp)

		cline = view.rendercells(rln, whole.render())
		if fai is not None:
			# Update annotation.
			yield cline

		if rln >= 0 and rln < edge:
			c = list(cursor.prepare_line_updates(self.keyboard.mapping, whole, hs))
			for (cellslice, celldelta) in c:
				ccursor = [celldelta(x) for x in cline[1][cellslice]]
				if ccursor:
					cline[1][cellslice] = ccursor
					yield ctx.__class__(sln, vx + cellslice.start, 1, len(ccursor)), ccursor

		# Translate codepoint offsets to cell offsets.
		hc = [
			whole.tell(whole.seek((0, 0), x, *m_cp)[0], *m_cell)
			for x in hs
		]
		si = list(self.structure.scale_ipositions(
			self.structure.indicate,
			(vx - rx, vy - ry),
			(hedge, edge),
			hc,
			v.snapshot(),
			focus.visible[1],
			focus.visible[0],
		))

		for pi in self.structure.r_indicators(si, rtypes=view.edges):
			(x, y), color, ic, bc = pi
			picell = cline[1][0].__class__(textcolor=color, codepoint=ord(ic))
			yield ctx.__class__(y, x, 1, 1), (picell,)

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
