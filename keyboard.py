"""
# Provides common mappings for keyboard based navigation and control.

# Modifying the mappings is not recommended, but is possible. Interacting
# with these mappings is the only way to modify the keyboard mappings used
# by &.console.

# [ Engineering ]
# Currently, there are no hooks for customizing bindings.

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
ctlm = events.Modifiers.construct(control=True)
shiftmeta = events.Modifiers.construct(meta=True, shift=True)

kmeta = (lambda x: ('literal', x, meta))
def lit(x, mods=0):
	return ('literal', x, mods)
def ctl(x, mods=0):
	return ('control', x, mods)
def nav(x, mods=0):
	return ('navigation', x, mods)

# events trapped and handled by the console. These are not forwarded to the refraction.
trap = Mapping()
trap.assign(lit('`', meta), 'console', ('toggle', 'prompt'))
# pane management
trap.assign(lit('j', meta), 'console', ('pane', 'rotate', 'refraction'), (1,))
trap.assign(lit('k', meta), 'console', ('pane', 'rotate', 'refraction'), (-1,))

trap.assign(ctl('i', meta), 'console', ('console', 'rotate', 'pane', 'forward'))
trap.assign(ctl('i', shiftmeta), 'console', ('console', 'rotate', 'pane', 'backward'))

# refraction control mapping
control = Mapping(('refraction', ('navigation', 'jump', 'character'), ()))
ca = control.assign
edit = Mapping(default = ('refraction', ('delta', 'insert', 'character'), ())) # insert
ea = edit.assign

# Keyboard mapping selection transitions.
if True:
	ca(lit('i'), 'refraction', ('transition', 'edit'),)
	ca(lit('O'), 'refraction', ('open', 'behind',))
	ca(lit('o'), 'refraction', ('open', 'ahead'))
	ca(ctl('o'), 'refraction', ('open', 'into'))

	ea(ctl('c'), 'refraction', ('edit', 'abort'))
	ea(ctl('d'), 'refraction', ('edit', 'commit')) # eof

# Prompt initialization bindings.
if True:
	ca(lit('o', meta), 'refraction', ('prepare', 'open'))
	ca(kmeta('l'), 'refraction', ('console', 'seek', 'line'))
	ca(ctl('w'), 'refraction', ('console', 'save'))

# distribution of commands across the vertical range.
ca(lit('y'), 'refraction', ('distribute', 'one'))
ca(lit('Y'), 'refraction', ('distribute', 'sequence'))
ca(ctl('y'), 'refraction', ('distribute', 'horizontal'))
ca(kmeta('y'), 'refraction', ('distribute', 'full')) # replacement for sequence?

# control
ca(ctl('c'), 'refraction', ('interrupt',))
ca(lit('c', meta), 'refraction', ('copy',))

#control.assign(('control', 'escape', 0), 'refraction', ('transition', 'exit'))
ca(ctl(' '), 'refraction', ('control', 'space'))
ca(ctl('m'), 'refraction', ('control', 'return'))

ca(lit('f'), 'refraction', ('navigation', 'horizontal', 'forward'))
ca(lit('d'), 'refraction', ('navigation', 'horizontal', 'backward'))
ca(lit('F'), 'refraction', ('navigation', 'horizontal', 'stop'))
ca(lit('D'), 'refraction', ('navigation', 'horizontal', 'start'))
ca(ctl('f'), 'refraction', ('navigation', 'horizontal', 'query', 'forward'))
ca(ctl('d'), 'refraction', ('navigation', 'horizontal', 'query', 'backward'))
ca(ctl('a'), 'refraction', ('navigation', 'move', 'bol'))
ca(ctl('e'), 'refraction', ('navigation', 'move', 'eol'))

ca(lit('s'), 'refraction', ('select', 'series',)) # Routing character sensitive.
ca(lit('S'), 'refraction', ('select', 'horizontal', 'line'))
ca(ctl('s'), 'refraction', ('console', 'series')) # reserved

ca(lit('e'), 'refraction', ('navigation', 'vertical', 'sections'))
ca(lit('E'), 'refraction', ('navigation', 'vertical', 'paging'))

ca(lit('j'), 'refraction', ('navigation', 'vertical', 'forward'))
ca(lit('k'), 'refraction', ('navigation', 'vertical', 'backward'))
ca(lit('J'), 'refraction', ('navigation', 'vertical', 'stop'))
ca(lit('K'), 'refraction', ('navigation', 'vertical', 'start'))
ca(ctl('j'), 'refraction', ('navigation', 'void', 'forward'))
ca(ctl('k'), 'refraction', ('navigation', 'void', 'backward'))

ca(lit('q'), 'refraction', ('navigation', 'range', 'enqueue'))
ca(lit('Q'), 'refraction', ('navigation', 'range', 'dequeue'))
ca(ctl('q'), 'refraction', ('print', 'unit'))
ca(lit('q', meta), 'refraction', ('console', 'search'))

ca(lit('t'), 'refraction', ('delta', 'translocate',))
ca(lit('T'), 'refraction', ('delta', 'transpose',))
ca(ctl('t'), 'refraction', ('delta', 'truncate'))

ca(lit('z'), 'refraction', ('place', 'stop',))
ca(lit('Z'), 'refraction', ('place', 'start',))
ca(ctl('z'), 'refraction', ('place', 'center'))

# [undo] log
ca(lit('u'), 'refraction', ('delta', 'undo',))
ca(lit('U'), 'refraction', ('delta', 'redo',))
ca(ctl('u'), 'refraction', ('redo',))

ca(lit('a'), 'refraction', ('select', 'adjacent', 'local'))
ca(lit('A'), 'refraction', ('select', 'adjacent'))

ca(lit('b'), 'refraction', ('select', 'block'))
ca(lit('B'), 'refraction', ('select', 'outerblock'))

ca(lit('n'), 'refraction', ('delta', 'split',))
ca(lit('N'), 'refraction', ('delta', 'join',))
ca(ctl('n'), 'refraction', ('',))

ca(lit('p'), 'refraction', ('paste', 'after'))
ca(lit('P'), 'refraction', ('paste', 'before',))
ca(ctl('p'), 'refraction', ('paste', 'into',))

ca(lit('l'), 'refraction', ('select', 'vertical', 'line'))
ca(lit('L'), 'refraction', ('select', 'block'))
ca(ctl('l'), 'refraction', ('console', 'reserved'))

for i in range(10):
	control.assign(lit(str(i)), 'refraction', ('index', 'reference'))

# character level movement
ca(ctl(' '), 'refraction', ('navigation', 'forward', 'character'))
ca(ctl('?'), 'refraction', ('navigation', 'backward', 'character'))

ca(nav('left'), 'refraction', ('window', 'horizontal', 'backward'))
ca(nav('right'), 'refraction', ('window', 'horizontal', 'forward'))
ca(nav('down'), 'refraction', ('window', 'vertical', 'forward'))
ca(nav('up'), 'refraction', ('window', 'vertical', 'backward'))

ca(nav('page-down'), 'refraction', ('window', 'vertical', 'forward', 'jump'))
ca(nav('page-up'), 'refraction', ('window', 'vertical', 'backward', 'jump'))
ca(nav('home'), 'refraction', ('window', 'vertical', 'start'))
ca(nav('end'), 'refraction', ('window', 'vertical', 'stop'))

ca(lit('m'), 'refraction', ('menu', 'primary'))
ca(lit('M'), 'refraction', ('menu', 'secondary'))

ca(lit('I'), 'refraction', ('delta', 'split'),) # split field (reserved)

ca(lit('c'), 'refraction', ('delta', 'substitute'),)
ca(lit('C'), 'refraction', ('delta', 'substitute', 'previous'),) # remap this

ca(lit('x'), 'refraction', ('delta', 'delete', 'forward'),)
ca(lit('X'), 'refraction', ('delta', 'delete', 'backward'),)
ca(ctl('x'), 'refraction', ('delta', 'delete', 'line'))
ca(kmeta('x'), 'refraction', ('delta', 'cut')) # Not Implemented

ca(lit('r'), 'refraction', ('delta', 'replace', 'character'),)
ca(lit('R'), 'refraction', ('delta', 'replace'),)
ca(ctl('r'), 'console', ('navigation', 'return'),)

ca(ctl('i'), 'refraction', ('delta', 'indent', 'increment'))
ca(ctl('i', shift), 'refraction', ('delta', 'indent', 'decrement'))
ca(ctl('v'), 'refraction', ('delta', 'indent', 'void'))

ca(ctl('c', 1), 'control', ('navigation', 'console')) # focus control console

# insert mode
ea(ctl('v'), 'refraction', ('edit', 'capture'))
ea(ctl('@'), 'refraction', ('delta', 'insert', 'space')) # Often Control-[Space]
ea(ctl(' ', shift), 'refraction', ('delta', 'insert', 'space'))
ea(ctl(' ', ctlm), 'refraction', ('delta', 'insert', 'space'))
ea(ctl(' '), 'refraction', ('delta', 'edit', 'insert', 'space'))

ea(ctl('?'), 'refraction', ('delta', 'delete', 'backward'))
ea(ctl('x'), 'refraction', ('delta', 'delete', 'forward'))

# these are mapped to keyboard names in order to allow class-level overrides
# and/or context sensitive action selection
ea(ctl('i'), 'refraction', ('delta', 'indent', 'increment'))
ea(ctl('i', shift), 'refraction', ('delta', 'indent', 'decrement'))
ea(ctl('m'), 'refraction', ('edit', 'return'))

ea(nav('left'), 'refraction', ('navigation', 'backward', 'character'))
ea(nav('right'), 'refraction', ('navigation', 'forward', 'character'))
ea(nav('up'), 'refraction', ('navigation', 'move', 'bol'))
ea(nav('down'), 'refraction', ('navigation', 'move', 'eol'))

ea(nav('left', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(nav('right', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(nav('up', shiftmeta), 'refraction', ('delta', 'insert', 'character'))
ea(nav('down', shiftmeta), 'refraction', ('delta', 'insert', 'character'))

ea(ctl('u'), 'refraction', ('delta', 'delete', 'tobol'))
ea(ctl('k'), 'refraction', ('delta', 'delete', 'toeol'))

ea(ctl('w'), 'refraction', ('delta', 'delete', 'backward', 'adjacent', 'class'))
ea(ctl('t'), 'refraction', ('delta', 'delete', 'forward', 'adjacent', 'class'))

ea(ctl('a'), 'refraction', ('navigation', 'move', 'bol'))
ea(ctl('e'), 'refraction', ('navigation', 'move', 'eol'))

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
	types.assign(lit(k), 'refraction', ('type', v))

types.assign(lit('l'), 'container', ('create', 'line'))

del ea, ca, nav, ctl, lit, shift, kmeta

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
