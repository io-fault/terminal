"""
# Default keyboard mappings.

# [ Properties ]

# /control/
	# Control mode mapping is for navigation and high-level manipulation.
# /edit/
	# Mode used to manage the insertion and removal of characters from fields.
# /capture/
	# Insert the exact character captured.
"""
from fault.terminal import events

class Mapping(object):
	"""
	# A mapping of commands and keys for binding shortcuts.

	# A mapping "context" is a reference to a target. For instance, a field, line, or
	# container.
	"""

	def __init__(self, default = None):
		self.default = default
		self.mapping = dict()
		self.reverse = dict()

	def assign(self, character, category, action, parameters = ()):
		"""
		# Assign the character sequence to action.
		"""
		key = (category, action, parameters)
		if key not in self.mapping:
			self.mapping[key] = set()

		value = character
		self.mapping[key].add(value)
		self.reverse[value] = key

	def event(self, key):
		"""
		# Return the action associated with the given keystroke.
		"""
		index = (key.type, key.identity, key.modifiers)
		return self.reverse.get(index, self.default)

shift = events.Modifiers.construct(shift=True)
meta = events.Modifiers.construct(meta=True)
ctlm = events.Modifiers.construct(control=True)
shiftmeta = events.Modifiers.construct(meta=True, shift=True)

kmeta = (lambda x: ('literal', x, meta))
def lit(x, mods=0):
	return ('literal', x, mods)
def ctl(x, mods=0):
	return ('control', x, mods)
def nav(x, mods=0):
	return 'navigation', (x, mods)

# events trapped and handled by the console. These are not forwarded to the refraction.
trap = Mapping()
trap.assign(lit('`', meta), 'navigation', ('prompt', 'toggle'))
# pane management
trap.assign(lit('j', meta), 'navigation', ('pane', 'rotate', 'refraction'), (1,))
trap.assign(lit('k', meta), 'navigation', ('pane', 'rotate', 'refraction'), (-1,))

trap.assign(ctl('i', meta), 'navigation', ('pane', 'rotate', 'forward'))
trap.assign(ctl('i', shiftmeta), 'navigation', ('pane', 'rotate', 'backward'))

# refraction control mapping
control = Mapping(('navigation', ('horizontal', 'jump', 'unit'), ()))
ca = control.assign
edit = Mapping(default = ('delta', ('insert', 'character'), ()))
ea = edit.assign

# capture keystroke
capture = Mapping(default = ('capture', (), ()))
ca(lit('r'), 'delta', ('replace', 'character'),)

if True:
	ca(lit('i'), 'delta', ('transition',))
	ca(lit('O'), 'delta', ('open', 'behind'))
	ca(lit('o'), 'delta', ('open', 'ahead'))
	ca(ctl('o'), 'delta', ('open', 'between'))

# Transaction management.
if True:
	ea(ctl('c'), 'transaction', ('abort',)) # Default SIGINT.
	ea(ctl('d'), 'transaction', ('commit',)) # Default EOF.
	ca(lit('u'), 'transaction', ('undo',))
	ca(lit('U'), 'transaction', ('redo',))

# Prompt initialization bindings.
if True:
	ca(lit('o', meta), 'console', ('prepare', 'open'))
	ca(kmeta('l'), 'console', ('prepare', 'seek'))
	ca(ctl('w'), 'console', ('prepare', 'write'))
	ca(lit('q', meta), 'console', ('prepare', 'search'))
	ca(ctl('q'), 'console', ('print', 'unit'))

# Cache operations.
if True:
	ca(lit('c', meta), 'delta', ('copy',))
	ca(lit('c', shiftmeta), 'delta', ('cut',))
	ca(lit('ξ'), 'delta', ('cut',))
	ca(lit('p'), 'delta', ('paste', 'after',))
	ca(lit('P'), 'delta', ('paste', 'before',))

# distribution of commands across the vertical range.
ca(lit('y'), 'console', ('distribute', 'one'))
ca(lit('Y'), 'console',('distribute', 'sequence'))
ca(ctl('y'), 'console', ('distribute', 'horizontal'))
ca(kmeta('y'), 'console', ('distribute', 'full'))

# Reactions to return/enter and space in insert mode.
ca(ctl('m'), 'delta', ('activate',))
ea(ctl('m'), 'delta', ('activate',))
ea(ctl('@'), 'delta', ('insert', 'space'))
ea(ctl(' ', shift), 'delta', ('insert', 'literal', 'space'))
ea(ctl(' ', ctlm), 'delta', ('insert', 'space'))
ea(ctl(' '), 'delta', ('insert', 'space'))

ca(lit('f'), 'navigation', ('horizontal', 'forward'))
ca(lit('d'), 'navigation', ('horizontal', 'backward'))
ca(lit('F'), 'navigation', ('horizontal', 'stop'))
ca(lit('D'), 'navigation', ('horizontal', 'start'))
ca(ctl('f'), 'navigation', ('horizontal', 'query', 'forward'))
ca(ctl('d'), 'navigation', ('horizontal', 'query', 'backward'))
ea(ctl('a'), 'navigation', ('horizontal', 'beginning'))
ca(ctl('a'), 'navigation', ('horizontal', 'beginning'))
ea(ctl('e'), 'navigation', ('horizontal', 'end'))
ca(ctl('e'), 'navigation', ('horizontal', 'end'))
ca(ctl(' '), 'navigation', ('horizontal', 'forward', 'unit'))
ca(ctl('?'), 'navigation', ('horizontal', 'backward', 'unit'))
ca(ctl('h'), 'navigation', ('horizontal', 'backward', 'unit'))
ea(nav('left'), 'navigation', ('horizontal', 'backward', 'unit'))
ea(nav('right'), 'navigation', ('horizontal', 'forward', 'unit'))
ea(nav('up'), 'navigation', ('horizontal', 'beginning'))
ea(nav('down'), 'navigation', ('horizontal', 'end'))

# Cursor range controls.
ca(lit('z'), 'navigation', ('place', 'stop',))
ca(lit('Z'), 'navigation', ('place', 'start',))
ca(ctl('z'), 'navigation', ('place', 'center'))
ca(lit('s'), 'navigation', ('horizontal', 'select', 'series',))
ca(lit('S'), 'navigation', ('horizontal', 'select', 'line'))
ca(lit('a'), 'navigation', ('vertical', 'select', 'adjacent', 'local'))
ca(lit('A'), 'navigation', ('vertical', 'select', 'adjacent'))
ca(lit('b'), 'navigation', ('vertical', 'select', 'block'))
ca(lit('B'), 'navigation', ('vertical', 'select', 'outerblock'))
ca(lit('l'), 'navigation', ('vertical', 'select', 'line'))
ca(lit('L'), 'navigation', ('vertical', 'select', 'block'))
ca(lit('e'), 'navigation', ('vertical', 'sections'))
ca(lit('E'), 'navigation', ('vertical', 'paging'))

ca(lit('j'), 'navigation', ('vertical', 'forward', 'unit'))
ca(lit('k'), 'navigation', ('vertical', 'backward', 'unit'))
ca(lit('J'), 'navigation', ('vertical', 'stop'))
ca(lit('K'), 'navigation', ('vertical', 'start'))
ca(ctl('j'), 'navigation', ('void', 'forward'))
ca(ctl('k'), 'navigation', ('void', 'backward'))

ca(lit('q'), 'navigation', ('range', 'enqueue'))
ca(lit('Q'), 'navigation', ('range', 'dequeue'))

ca(lit('t'), 'delta', ('move', 'range'))
ca(lit('T'), 'delta', ('transpose', 'range'))
ca(ctl('t'), 'delta', ('truncate', 'range'))

ca(lit('n'), 'delta', ('line', 'break',))
ca(lit('N'), 'delta', ('line', 'join',))

for i in range(10):
	control.assign(lit(str(i)), 'navigation', ('index', 'reference'))

ca(nav('left'), 'navigation', ('window', 'horizontal', 'backward'))
ca(nav('right'), 'navigation', ('window', 'horizontal', 'forward'))
ca(nav('down'), 'navigation', ('window', 'vertical', 'forward'))
ca(nav('up'), 'navigation', ('window', 'vertical', 'backward'))

ca(nav('page-down'), 'navigation', ('window', 'vertical', 'forward', 'jump'))
ca(nav('page-up'), 'navigation', ('window', 'vertical', 'backward', 'jump'))
ca(nav('home'), 'navigation', ('window', 'vertical', 'start'))
ca(nav('end'), 'navigation', ('window', 'vertical', 'stop'))

ca(lit('I'), 'delta', ('split',)) # split field (reserved)

ca(lit('c'), 'delta', ('horizontal', 'substitute', 'range'))
ca(lit('C'), 'delta', ('horizontal', 'substitute', 'again'))

ca(lit('x'), 'delta', ('delete', 'forward', 'unit'))
ca(lit('X'), 'delta', ('delete', 'backward', 'unit'))
ca(ctl('x'), 'delta', ('vertical', 'delete', 'unit'))

ca(ctl('i'), 'delta', ('indent', 'increment'))
ca(ctl('i', shift), 'delta', ('indent', 'decrement'))
ca(ctl('v'), 'delta', ('indent', 'void'))

ea(('paste', 'start', events.Modifiers(0)), 'transaction', ('checkpoint'))
#ea(('paste', 'stop', events.Modifiers(0)), 'transaction', ('checkpoint'))
ea(('data', 'paste', events.Modifiers(0)), 'delta', ('insert', 'data'))
ea(ctl('v'), 'delta', ('insert', 'capture'))

ea(ctl('?'), 'delta', ('delete', 'backward', 'unit'))
ea(ctl('h'), 'delta', ('delete', 'backward', 'unit'))
ea(ctl('x'), 'delta', ('delete', 'forward', 'unit'))

# these are mapped to keyboard names in order to allow class-level overrides
# and/or context sensitive action selection
ea(ctl('i'), 'delta', ('indent', 'increment'))
ea(ctl('i', shift), 'delta', ('indent', 'decrement'))

ea(ctl('u'), 'delta', ('delete', 'leading'))
ea(ctl('k'), 'delta', ('delete', 'following'))

ea(ctl('w'), 'delta', ('delete', 'backward', 'adjacent', 'class'))
ea(ctl('t'), 'delta', ('delete', 'forward', 'adjacent', 'class'))

del ea, ca, nav, ctl, lit, shift, kmeta

standard = {
	'control': control,
	'edit': edit,
	'capture': capture,
}

class Selection(object):
	"""
	# A set of mappings used to interact with a matrix.
	"""
	__slots__ = ('index', 'current')

	@property
	def mapping(self):
		"""
		# Get the currently selected mapping by the defined name.
		"""
		return self.current[0]

	def __init__(self, index):
		self.index = index
		self.current = None

	def set(self, name):
		self.current = (name, self.index[name])
		return self.current

	def event(self, key):
		"""
		# Look up the event using the currently selected mapping.
		"""
		return (self.current[0], self.current[1].event(key))

	@classmethod
	def standard(Class):
		return Class(standard)
