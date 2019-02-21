"""
# Provides common mappings for keyboard based navigation and control.

# Modifying the mappings is not recommended, but is possible. Interacting
# with these mappings is the only way to modify the keyboard mappings used
# by &.console.

# ! FUTURE:
	# The (system/file)`~/.fault/console.py` script can be used to customize
	# the mappings. When a Session is created in an application, the callbacks
	# defined in the module can be used to do further initialization.

# [ Properties ]

# /trap/
	# Console level events. Key events mapped here are trapped and are
	# not propagated to Refractions. This is the "global" mapping.
# /control/
	# Control mode mapping is for navigation and high-level manipulation.
# /edit/
	# Mode used to manage the insertion and removal of characters from fields.
# /capture/
	# ...
# /types/
	# Mode used to select field types for custom interactions.
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

	def assign(self, character, context, action, parameters = ()):
		"""
		# Assign the character sequence to action.
		"""
		key = (context, action, parameters)
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
shiftmeta = events.Modifiers.construct(meta=True, shift=True)

literal = (lambda x: ('literal', x, 0))
kmeta = (lambda x: ('literal', x, meta))
def ctl(x, mods=0):
	return ('control', x, mods)
nav = (lambda x: ('navigation', x, 0))
shiftnav = (lambda x: ('navigation', x, shift))

# events trapped and handled by the console. These are not forwarded to the refraction.
trap = Mapping()
trap.assign(('literal', '`', meta), 'console', ('toggle', 'prompt'))
# pane management
trap.assign(('literal', 'j', meta), 'console', ('pane', 'rotate', 'refraction'), (1,))
trap.assign(('literal', 'k', meta), 'console', ('pane', 'rotate', 'refraction'), (-1,))

trap.assign(ctl('i', meta), 'console', ('console', 'rotate', 'pane', 'forward'))
trap.assign(ctl('i', shiftmeta), 'console', ('console', 'rotate', 'pane', 'backward'))

# refraction control mapping
control = Mapping(('refraction', ('navigation', 'jump', 'character'), ()))
ca = control.assign

ca(('literal', 'o', meta), 'refraction', ('prepare', 'open'))

# distribution of commands across the vertical range.
ca(literal('y'), 'refraction', ('distribute', 'one'))
ca(literal('Y'), 'refraction', ('distribute', 'sequence'))
ca(ctl('y'), 'refraction', ('distribute', 'horizontal'))
ca(kmeta('y'), 'refraction', ('distribute', 'full')) # replacement for sequence?

# control
ca(ctl('c'), 'refraction', ('interrupt',))
ca(('literal', 'c', meta), 'refraction', ('copy',))

#control.assign(('control', 'escape', 0), 'refraction', ('transition', 'exit'))
ca(ctl(' '), 'refraction', ('control', 'space'))
ca(ctl('m'), 'refraction', ('control', 'return'))

ca(literal('f'), 'refraction', ('navigation', 'horizontal', 'forward'))
ca(literal('d'), 'refraction', ('navigation', 'horizontal', 'backward'))
ca(literal('F'), 'refraction', ('navigation', 'horizontal', 'stop'))
ca(literal('D'), 'refraction', ('navigation', 'horizontal', 'start'))
ca(ctl('f'), 'refraction', ('navigation', 'horizontal', 'query', 'forward'))
ca(ctl('d'), 'refraction', ('navigation', 'horizontal', 'query', 'backward'))

ca(literal('s'), 'refraction', ('select', 'series',))
ca(literal('S'), 'refraction', ('select', 'horizontal', 'line'))
ca(ctl('s'), 'refraction', ('console', 'series')) # reserved

ca(literal('e'), 'refraction', ('navigation', 'vertical', 'sections'))
ca(literal('E'), 'refraction', ('navigation', 'vertical', 'paging'))
ca(ctl('e'), 'refraction', ('print', 'unit'))

# temporary
ca(ctl('w'), 'refraction', ('console', 'save'))

ca(literal('j'), 'refraction', ('navigation', 'vertical', 'forward'))
ca(literal('k'), 'refraction', ('navigation', 'vertical', 'backward'))
ca(literal('J'), 'refraction', ('navigation', 'vertical', 'stop'))
ca(literal('K'), 'refraction', ('navigation', 'vertical', 'start'))
ca(ctl('j'), 'refraction', ('navigation', 'void', 'forward'))
ca(ctl('k'), 'refraction', ('navigation', 'void', 'backward'))

ca(literal('O'), 'refraction', ('open', 'behind',))
ca(literal('o'), 'refraction', ('open', 'ahead'))
ca(ctl('o'), 'refraction', ('open', 'into'))

ca(literal('q'), 'refraction', ('navigation', 'range', 'enqueue'))
ca(literal('Q'), 'refraction', ('navigation', 'range', 'dequeue'))
ca(ctl('q'), 'refraction', ('',)) # spare
ca(('literal', 'q', meta), 'refraction', ('console', 'search'))

#ca(literal('v'), 'refraction', ('navigation', 'void', 'forward',))
#ca(literal('V'), 'refraction', ('navigation', 'void', 'backward',))
#ca(ctl('v'), 'refraction', ('',)) # spare

ca(literal('t'), 'refraction', ('delta', 'translocate',))
ca(literal('T'), 'refraction', ('delta', 'transpose',))
ca(ctl('t'), 'refraction', ('delta', 'truncate'))

ca(literal('z'), 'refraction', ('place', 'stop',))
ca(literal('Z'), 'refraction', ('place', 'start',))
ca(ctl('z'), 'refraction', ('place', 'center'))

# [undo] log
ca(literal('u'), 'refraction', ('delta', 'undo',))
ca(literal('U'), 'refraction', ('delta', 'redo',))
ca(ctl('u'), 'refraction', ('redo',))

ca(literal('a'), 'refraction', ('select', 'adjacent', 'local'))
ca(literal('A'), 'refraction', ('select', 'adjacent'))

ca(literal('b'), 'refraction', ('select', 'block'))
ca(literal('B'), 'refraction', ('select', 'outerblock'))

ca(literal('n'), 'refraction', ('delta', 'split',))
ca(literal('N'), 'refraction', ('delta', 'join',))
ca(ctl('n'), 'refraction', ('',))

ca(literal('p'), 'refraction', ('paste', 'after'))
ca(literal('P'), 'refraction', ('paste', 'before',))
ca(ctl('p'), 'refraction', ('paste', 'into',))

ca(literal('l'), 'refraction', ('select', 'vertical', 'line'))
ca(literal('L'), 'refraction', ('select', 'block'))
ca(ctl('l'), 'refraction', ('console', 'reserved'))
ca(kmeta('l'), 'refraction', ('console', 'seek', 'line'))

for i in range(10):
	control.assign(literal(str(i)), 'refraction', ('index', 'reference'))

# character level movement
ca(ctl(' '), 'refraction', ('navigation', 'forward', 'character'))
ca(ctl('?'), 'refraction', ('navigation', 'backward', 'character'))

ca(nav('left'), 'refraction', ('window', 'horizontal', 'forward'))
ca(nav('right'), 'refraction', ('window', 'horizontal', 'backward'))
ca(nav('down'), 'refraction', ('window', 'vertical', 'forward'))
ca(nav('up'), 'refraction', ('window', 'vertical', 'backward'))

ca(nav('pagedown'), 'refraction', ('window', 'vertical', 'forward', 'jump'))
ca(nav('pageup'), 'refraction', ('window', 'vertical', 'backward', 'jump'))
ca(nav('home'), 'refraction', ('window', 'vertical', 'start'))
ca(nav('end'), 'refraction', ('window', 'vertical', 'stop'))

ca(literal('m'), 'refraction', ('menu', 'primary'))
ca(literal('M'), 'refraction', ('menu', 'secondary'))

ca(literal('i'), 'refraction', ('transition', 'edit'),)
ca(literal('I'), 'refraction', ('delta', 'split'),) # split field (reserved)

ca(literal('c'), 'refraction', ('delta', 'substitute'),)
ca(literal('C'), 'refraction', ('delta', 'substitute', 'previous'),) # remap this

ca(literal('x'), 'refraction', ('delta', 'delete', 'forward'),)
ca(literal('X'), 'refraction', ('delta', 'delete', 'backward'),)
ca(ctl('x'), 'refraction', ('delta', 'delete', 'line'))
ca(kmeta('x'), 'refraction', ('delta', 'cut')) # Not Implemented

ca(literal('r'), 'refraction', ('delta', 'replace', 'character'),)
ca(literal('R'), 'refraction', ('delta', 'replace'),)
ca(ctl('r'), 'console', ('navigation', 'return'),)

ca(ctl('i'), 'refraction', ('delta', 'indent', 'increment'))
ca(ctl('i', shift), 'refraction', ('delta', 'indent', 'decrement'))
ca(ctl('v'), 'refraction', ('delta', 'indent', 'void'))

ca(ctl('c', 1), 'control', ('navigation', 'console')) # focus control console
del ca

# insert mode
edit = Mapping(default = ('refraction', ('delta', 'insert', 'character'), ())) # insert
ea = edit.assign
ea(ctl('@'), 'refraction', ('delta', 'insert', 'space')) # literal space

ea(ctl('c'), 'refraction', ('edit', 'abort'))
ea(ctl('d'), 'refraction', ('edit', 'commit')) # eof
ea(ctl('v'), 'refraction', ('edit', 'capture'))

ea(ctl('?'), 'refraction', ('delta', 'delete', 'backward'))
ea(ctl('x'), 'refraction', ('delta', 'delete', 'forward'))

# these are mapped to keyboard names in order to allow class-level overrides
# and/or context sensitive action selection
ea(ctl(' '), 'refraction', ('delta', 'edit', 'insert', 'space'))
ea(ctl('i'), 'refraction', ('edit', 'tab'))
ea(ctl('i', shift), 'refraction', ('edit', 'shift', 'tab'))
ea(ctl('m'), 'refraction', ('edit', 'return'))

ea(('navigation', 'left', 0), 'refraction', ('navigation', 'backward', 'character'))
ea(('navigation', 'right', 0), 'refraction', ('navigation', 'forward', 'character'))
ea(('navigation', 'up', 0), 'refraction', ('navigation', 'move', 'bol'))
ea(('navigation', 'down', 0), 'refraction', ('navigation', 'move', 'eol'))

ea(('navigation', 'left', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(('navigation', 'right', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(('navigation', 'up', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(('navigation', 'down', shiftmeta), 'refraction', ('delta', 'insert', 'character'))

ea(ctl('u'), 'refraction', ('delta', 'delete', 'tobol'))
ea(ctl('k'), 'refraction', ('delta', 'delete', 'toeol'))

ea(ctl('w'), 'refraction', ('delta', 'delete', 'backward', 'adjacent', 'class'))
ea(ctl('t'), 'refraction', ('delta', 'delete', 'forward', 'adjacent', 'class'))

ea(ctl('a'), 'refraction', ('navigation', 'move', 'bol'))
ea(ctl('e'), 'refraction', ('navigation', 'move', 'eol'))
del ea

# capture keystroke
capture = Mapping(default = ('refraction', ('capture',), ()))

# field creation and type selection
types = Mapping()
field_type_mnemonics = {
	'i': 'integer',
	't': 'text',
	'"': 'quotation',
	"'": 'quotation',
	'd': 'date',
	'T': 'timestamp',
	'n': 'internet', # address
	'r': 'reference', # contextual reference (variables, environment)
}
for k, v in field_type_mnemonics.items():
	types.assign(literal(k), 'refraction', ('type',), (v,))

types.assign(literal('l'), 'container', ('create', 'line'))

del nav, ctl, literal, shift

standard = {
	'control': control,
	'edit': edit,
	'capture': capture,
	'types': types,
}

class Selection(object):
	"""
	# A set of mappings used to interact with objects.
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
