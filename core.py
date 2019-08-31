import functools
import operator
import collections

from fault.kernel import core as kcore
from fault.terminal import matrix

from . import keyboard

class Position(object):
	"""
	# Mutable position state for managing the position of a cursor with respect to a range.
	# No constraints are enforced and position coherency is considered subjective.

	# [ Properties ]
	# /datum/
		# The absolute position. (start)
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

	def move(self, location = 0, perspective = 0):
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

	def halt(self):
		"""
		# Halt the position by adjusting the &magnitude to match the position of the
		# offset.
		"""
		self.magnitude = self.offset

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
			self.datum += quantity
			return
		elif roffset > self.magnitude:
			return

		self.magnitude += quantity

		# if the contraction occurred at or before the position,
		# move the offset back as well in order to keep the position
		# consistent.
		if roffset <= self.offset:
			self.offset += quantity

	def expand(self, offset, quantity):
		"""
		# Adjust, increase, the magnitude relative to a particular offset.
		"""
		return self.contract(offset, -quantity)

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

class Vector(object):
	"""
	# A pair of &Position instances describing an area and point on a two dimensional plane.

	# Primarily this exists to provide methods that will often be used simultaneously on the vertical
	# and horizontal positions. State snapshots and restoration being common or likely.

	# [ Properties ]
	# /horizontal/
		# The horizontal &Position.
	# /vertical/
		# The vertical &Position.
	"""

	def __len__(self):
		return 2

	def __getitem__(self, index:int):
		if index:
			if index != 1:
				raise IndexError("terminal poisition vectors only have two entries")
			return self.vertical
		return self.horizontal

	def __iter__(self):
		return (self.horizontal, self.vertical).__iter__()

	def clear(self):
		"""
		# Zero the horizontal and vertical positions.
		"""
		self.horizontal.clear()
		self.vertical.clear()

	def move(self, x, y):
		"""
		# Move the positions relative to their current state.
		# This method should be used for cases when applying a function:

		#!/pl/python
			for x in range(...):
				vector.move(x, f(x))
				draw(vector)
		"""
		if x:
			self.horizontal.update(x)
		if y:
			self.vertical.update(y)

	def get(self):
		"""
		# Get the absolute horizontal and vertical position as a 2-tuple.
		"""
		return Point((self.horizontal.get(), self.vertical.get()))

	def __init__(self):
		"""
		# Create a &Vector whose positions are initialized to zero.
		"""
		self.horizontal = Position()
		self.vertical = Position()

	def snapshot(self):
		return (self.horizontal.snapshot(), self.vertical.snapshot())

	def restore(self, snapshot):
		self.horizontal.restore(snapshot[0])
		self.vertical.restore(snapshot[1])

class Cache(object):
	"""
	# Mapping interface for user trans-refraction communication. (Local Clipboard)

	# Maintains a set of slots for storing a sequence of typed objects; the latest item
	# in the slot being the default. A sequence is used in order to maintain a history of
	# cached objects. The configured limit restricts the number recalled.

	# Console clipboard.
	"""

	__slots__ = ('storage', 'limit')
	Storage = dict
	Sequence = collections.deque

	def __init__(self, limit = 8):
		self.storage = self.Storage()
		self.limit = limit

	def allocate(self, *keys):
		"""
		# Initialize a cache slot.
		"""
		for k in keys:
			if k not in self.storage:
				self.storage[k] = self.Sequence()

	def index(self):
		"""
		# Return a sequence of storage slots.
		"""
		return self.storage.keys()

	def put(self, key, cobject):
		"""
		# Put the given object as the cache entry.
		"""
		slot = self.storage[key]
		type, object = cobject
		slot.append((type, object))

		if len(slot) > self.limit:
			slot.popleft()

	def get(self, key, offset = 0):
		"""
		# Get the contents of the cache slot.
		"""
		r = self.storage[key][-(1 + offset)]

		if r[0] == 'reference':
			r = r[1]()

		return r

	def clear(self, key):
		"""
		# Remove the all the contents of the given slot.
		"""
		self.storage[key].clear()

class Refraction(kcore.Processor):
	"""
	# A Refraction of a source onto a connected area of the display.

	# Refraction resources are used by Console transformers to manage the parts
	# of the display.
	"""

	create_keyboard_mapping = keyboard.Selection.standard
	default_keyboard_mapping = 'edit'

	@property
	def horizontal(self):
		"""
		# The current working horizontal position.
		"""
		return self.vector.horizontal

	@property
	def vertical(self):
		"""
		# The current working vertical position.
		"""
		return self.vector.vertical

	@property
	def last_axis(self):
		"""
		# The recently used axis.
		"""
		if self.vector_last_axis is self.horizontal:
			return 'horizontal'
		else:
			return 'vertical'

	@property
	def axis(self):
		"""
		# Return the &Position of the last axis used.
		"""
		return self.vector_last_axis

	@property
	def keyset(self):
		return self.keyboard.current

	def __init__(self):
		self.movement = False
		self.page = [] # Phrase buffer.
		self.page_cells = [] # Sum of cells.

		self.view = None
		self.pane = None # pane index of refraction; None if not a pane or hidden

		# keeps track of horizontal positions that are modified for cursor and range display
		self.horizontal_positions = {}
		self.horizontal_range = None

		# View location of the refraction.
		self.window = Vector()
		# Physical location of the refraction.
		self.vector = Vector()

		self.vector_last_axis = self.vector.vertical # last used axis
		self.vertical_index = 0 # the focus line

		self.range_queue = collections.deque()

		# Recorded snapshot of vector and window.
		# Used by Console to clear outdated cursor positions.
		self.snapshot = (self.vector.snapshot(), self.window.snapshot())

		self.keyboard = self.create_keyboard_mapping() # per-refraction to maintain state
		self.keyboard.set(self.default_keyboard_mapping)
		self.distributing = False

	@staticmethod
	@functools.lru_cache(16)
	def event_method(target, event):
		return 'event_' + '_'.join(event)

	def route(self, event, scrollmap={-1:'backward', 1:'forward'}):
		"""
		# Route the event to the target given the current processing state.
		"""

		if event.type == 'scrolled':
			point, mevent, activation = event.identity

			if mevent in scrollmap:
				return (None, ('refraction',
					('window', 'vertical', scrollmap[mevent]), (activation, point,)
				))
		elif event.type == 'click':
			point, key_id, delay = event.identity
			return (None, ('refraction', ('select', 'absolute'), (point[0], point[1])))
		else:
			mapping, event = self.keyboard.event(event)
			if event is None:
				# report no such binding
				return None

			return (mapping, event)

	def key(self, console, event, getattr=getattr, range=range):
		"""
		# Process the event.
		"""
		routing = self.route(event)
		if routing is None:
			return ()

		mapping, (target_id, event_selection, params) = routing
		method_name = self.event_method(target_id, event_selection)
		method = getattr(self, method_name)

		if self.distributing and event_selection[0] == 'delta':
			self.clear_horizontal_indicators()
			v = self.vertical
			h = self.horizontal

			if abs(v.magnitude) == 0:
				# Horizontal distribution.
				hs = h.get()
				h.move(1, -1)
				hs = self.horizontal.snapshot()

				for i in range(h.magnitude-1, -1, -1):
					method(event, *params)
					h.move(-1)
			else:
				# Vertical distribution.
				vs = v.get()
				v.move(1, -1)
				hs = self.horizontal.snapshot()

				for i in range(v.magnitude, 0, -1):
					h.restore(hs)
					self.update_unit()
					method(event, *params)
					v.move(-1)

				v.set(vs)
				self.update_vertical_state()

			rob = None
			if self.distribute_once == True:
				self.distributing = not self.distributing
				self.distribute_once = None
		else:
			rob = method(event, *params)

		if self.sector.refraction is self:
			self.update_horizontal_indicators()

		return rob

	def event_distribute_sequence(self, event):
		self.distributing = not self.distributing
		self.distribute_once = False

	def event_distribute_one(self, event):
		self.distributing = not self.distributing
		self.distribute_once = True

	def event_prepare_open(self, event):
		console = self.sector
		return console.event_prepare_open(event)

	def adjust(self, point, dimensions):
		"""
		# Adjust the positioning and size of the view. &point is a pair of positive integers
		# describing the top-right corner on the screen and dimensions is a pair of positive
		# integers describing the width.

		# Adjustments are conditionally passed to a view.
		"""
		if self.view is not None:
			self.view.context_set_position(point)
			self.view.context_set_dimensions(dimensions)
			self.calibrate(dimensions)

	def calibrate(self, dimensions):
		"""
		# Called when the refraction is adjusted.
		"""
		w = self.window
		w.horizontal.configure(w.horizontal.datum, dimensions[0], 0)
		w.vertical.configure(w.vertical.datum, dimensions[1], 0)

	def conceal(self):
		"""
		# Called when the refraction is hidden from the display.
		"""
		pass

	def reveal(self):
		"""
		# Called when the refraction is revealed. May not be focused.
		"""
		pass

	@property
	def revealed(self):
		"""
		# Whether the refraction is currently visible.
		"""
		return self in self.sector.visible

	def focus(self):
		"""
		# Set position indicators and activate cursor.
		"""
		console = self.sector
		events = console.set_position_indicators(self)
		console.f_emit([events])

	@property
	def focused(self):
		"""
		# Whether the refraction is the current focus; receives key events.
		"""
		return self.sector.refraction is self

	def blur(self):
		"""
		# Clear position indicators and lock cursor.
		"""
		console = self.sector
		events = console.clear_position_indicators(self)
		console.f_emit([events])

	def connect(self, view):
		"""
		# Connect the area to the refraction for displaying the units.

		# Connect &None in order to conceal.
		"""
		self.view = view

		if view is None:
			return self.conceal()
		else:
			return self.reveal()

	def clear(self):
		"""
		# Clear the refraction state.
		"""
		pass

	def update(self, start, stop, *lines):
		"""
		# Render all the display lines in the given ranges.
		"""
		pass

	def render(self, start, stop):
		pass

	def refresh(self):
		"""
		# Render all lines in the refraction.
		"""
		pass
