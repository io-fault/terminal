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
trap.assign(lit('`', meta), 'console', ('navigation', 'prompt', 'toggle'))
# pane management
trap.assign(lit('j', meta), 'console', ('navigation', 'pane', 'rotate', 'refraction'), (1,))
trap.assign(lit('k', meta), 'console', ('navigation', 'pane', 'rotate', 'refraction'), (-1,))

trap.assign(ctl('i', meta), 'console', ('navigation', 'pane', 'rotate', 'forward'))
trap.assign(ctl('i', shiftmeta), 'console', ('navigation', 'pane', 'rotate', 'backward'))

# refraction control mapping
control = Mapping(('refraction', ('navigation', 'horizontal', 'jump', 'unit'), ()))
ca = control.assign
edit = Mapping(default = ('refraction', ('delta', 'insert', 'character'), ())) # insert
ea = edit.assign

if True:
	ca(lit('i'), 'refraction', ('delta', 'transition'))
	ca(lit('O'), 'refraction', ('delta', 'open', 'behind'))
	ca(lit('o'), 'refraction', ('delta', 'open', 'ahead'))
	ca(ctl('o'), 'refraction', ('delta', 'open', 'between'))

# Transaction management.
if True:
	ea(ctl('c'), 'refraction', ('transaction', 'abort')) # Default SIGINT.
	ea(ctl('d'), 'refraction', ('transaction', 'commit')) # Default EOF.
	ca(lit('u'), 'refraction', ('transaction', 'undo'))
	ca(lit('U'), 'refraction', ('transaction', 'redo'))

# Prompt initialization bindings.
if True:
	ca(lit('o', meta), 'refraction', ('console', 'prepare', 'open'))
	ca(kmeta('l'), 'refraction', ('console', 'prepare', 'seek'))
	ca(ctl('w'), 'refraction', ('console', 'prepare', 'write'))
	ca(lit('q', meta), 'refraction', ('console', 'prepare', 'search'))
	ca(ctl('q'), 'refraction', ('console', 'print', 'unit'))

# Cache operations.
if True:
	ca(lit('c', meta), 'refraction', ('delta', 'copy',))
	ca(lit('c', shiftmeta), 'refraction', ('delta', 'cut',))
	ca(lit('ξ'), 'refraction', ('delta', 'cut',))
	ca(lit('p'), 'refraction', ('delta', 'paste', 'after'))
	ca(lit('P'), 'refraction', ('delta', 'paste', 'before',))

# distribution of commands across the vertical range.
ca(lit('y'), 'refraction', ('distribute', 'one'))
ca(lit('Y'), 'refraction', ('distribute', 'sequence'))
ca(ctl('y'), 'refraction', ('distribute', 'horizontal'))
ca(kmeta('y'), 'refraction', ('distribute', 'full')) # replacement for sequence?

# Reactions to return/enter and space in insert mode.
ca(ctl('c'), 'refraction', ('interrupt',))
ca(ctl('m'), 'refraction', ('delta', 'activate'))
ea(ctl('m'), 'refraction', ('delta', 'activate'))
ea(ctl('@'), 'refraction', ('delta', 'insert', 'space'))
ea(ctl(' ', shift), 'refraction', ('delta', 'insert', 'literal', 'space'))
ea(ctl(' ', ctlm), 'refraction', ('delta', 'insert', 'space'))
ea(ctl(' '), 'refraction', ('delta', 'insert', 'space'))

ca(lit('f'), 'refraction', ('navigation', 'horizontal', 'forward'))
ca(lit('d'), 'refraction', ('navigation', 'horizontal', 'backward'))
ca(lit('F'), 'refraction', ('navigation', 'horizontal', 'stop'))
ca(lit('D'), 'refraction', ('navigation', 'horizontal', 'start'))
ca(ctl('f'), 'refraction', ('navigation', 'horizontal', 'query', 'forward'))
ca(ctl('d'), 'refraction', ('navigation', 'horizontal', 'query', 'backward'))
ea(ctl('a'), 'refraction', ('navigation', 'horizontal', 'beginning'))
ca(ctl('a'), 'refraction', ('navigation', 'horizontal', 'beginning'))
ea(ctl('e'), 'refraction', ('navigation', 'horizontal', 'end'))
ca(ctl('e'), 'refraction', ('navigation', 'horizontal', 'end'))
ca(ctl(' '), 'refraction', ('navigation', 'horizontal', 'forward', 'unit'))
ca(ctl('?'), 'refraction', ('navigation', 'horizontal', 'backward', 'unit'))
ca(ctl('h'), 'refraction', ('navigation', 'horizontal', 'backward', 'unit'))
ea(nav('left'), 'refraction', ('navigation', 'horizontal', 'backward', 'unit'))
ea(nav('right'), 'refraction', ('navigation', 'horizontal', 'forward', 'unit'))
ea(nav('up'), 'refraction', ('navigation', 'horizontal', 'beginning'))
ea(nav('down'), 'refraction', ('navigation', 'horizontal', 'end'))

# Cursor range controls.
ca(lit('z'), 'refraction', ('navigation', 'place', 'stop',))
ca(lit('Z'), 'refraction', ('navigation', 'place', 'start',))
ca(ctl('z'), 'refraction', ('navigation', 'place', 'center'))
ca(lit('s'), 'refraction', ('navigation', 'horizontal', 'select', 'series',))
ca(lit('S'), 'refraction', ('navigation', 'horizontal', 'select', 'line'))
ca(lit('a'), 'refraction', ('navigation', 'vertical', 'select', 'adjacent', 'local'))
ca(lit('A'), 'refraction', ('navigation', 'vertical', 'select', 'adjacent'))
ca(lit('b'), 'refraction', ('navigation', 'vertical', 'select', 'block'))
ca(lit('B'), 'refraction', ('navigation', 'vertical', 'select', 'outerblock'))
ca(lit('l'), 'refraction', ('navigation', 'vertical', 'select', 'line'))
ca(lit('L'), 'refraction', ('navigation', 'vertical', 'select', 'block'))
ca(lit('e'), 'refraction', ('navigation', 'vertical', 'sections'))
ca(lit('E'), 'refraction', ('navigation', 'vertical', 'paging'))

ca(lit('j'), 'refraction', ('navigation', 'vertical', 'forward', 'unit'))
ca(lit('k'), 'refraction', ('navigation', 'vertical', 'backward', 'unit'))
ca(lit('J'), 'refraction', ('navigation', 'vertical', 'stop'))
ca(lit('K'), 'refraction', ('navigation', 'vertical', 'start'))
ca(ctl('j'), 'refraction', ('navigation', 'void', 'forward'))
ca(ctl('k'), 'refraction', ('navigation', 'void', 'backward'))


ca(lit('q'), 'refraction', ('navigation', 'range', 'enqueue'))
ca(lit('Q'), 'refraction', ('navigation', 'range', 'dequeue'))

ca(lit('t'), 'refraction', ('delta', 'move', 'range'))
ca(lit('T'), 'refraction', ('delta', 'transpose', 'range'))
ca(ctl('t'), 'refraction', ('delta', 'truncate', 'range'))

ca(lit('n'), 'refraction', ('delta', 'line', 'break',))
ca(lit('N'), 'refraction', ('delta', 'line', 'join',))

for i in range(10):
	control.assign(lit(str(i)), 'refraction', ('index', 'reference'))

ca(nav('left'), 'refraction', ('navigation', 'window', 'horizontal', 'backward'))
ca(nav('right'), 'refraction', ('navigation', 'window', 'horizontal', 'forward'))
ca(nav('down'), 'refraction', ('navigation', 'window', 'vertical', 'forward'))
ca(nav('up'), 'refraction', ('navigation', 'window', 'vertical', 'backward'))

ca(nav('page-down'), 'refraction', ('navigation', 'window', 'vertical', 'forward', 'jump'))
ca(nav('page-up'), 'refraction', ('navigation', 'window', 'vertical', 'backward', 'jump'))
ca(nav('home'), 'refraction', ('navigation', 'window', 'vertical', 'start'))
ca(nav('end'), 'refraction', ('navigation', 'window', 'vertical', 'stop'))

ca(lit('I'), 'refraction', ('delta', 'split'),) # split field (reserved)

ca(lit('c'), 'refraction', ('delta', 'horizontal', 'substitute', 'range'),)
ca(lit('C'), 'refraction', ('delta', 'horizontal', 'substitute', 'again'),)

ca(lit('x'), 'refraction', ('delta', 'delete', 'forward', 'unit'))
ca(lit('X'), 'refraction', ('delta', 'delete', 'backward', 'unit'))
ca(ctl('x'), 'refraction', ('delta', 'vertical', 'delete', 'unit'))

ca(lit('r'), 'refraction', ('delta', 'replace', 'character'),)

ca(ctl('i'), 'refraction', ('delta', 'indent', 'increment'))
ca(ctl('i', shift), 'refraction', ('delta', 'indent', 'decrement'))
ca(ctl('v'), 'refraction', ('delta', 'indent', 'void'))

ca(ctl('c', 1), 'control', ('navigation', 'console')) # focus control console

ea(('paste', 'start', events.Modifiers(0)), 'refraction', ('transaction', 'checkpoint'))
#ea(('paste', 'stop', events.Modifiers(0)), 'refraction', ('transaction', 'checkpoint',))
ea(('data', 'paste', events.Modifiers(0)), 'refraction', ('delta', 'insert', 'data'))
ea(ctl('v'), 'refraction', ('delta', 'insert', 'capture'))

ea(ctl('?'), 'refraction', ('delta', 'delete', 'backward', 'unit'))
ea(ctl('h'), 'refraction', ('delta', 'delete', 'backward', 'unit'))
ea(ctl('x'), 'refraction', ('delta', 'delete', 'forward', 'unit'))

# these are mapped to keyboard names in order to allow class-level overrides
# and/or context sensitive action selection
ea(ctl('i'), 'refraction', ('delta', 'indent', 'increment'))
ea(ctl('i', shift), 'refraction', ('delta', 'indent', 'decrement'))

ea(ctl('u'), 'refraction', ('delta', 'delete', 'leading'))
ea(ctl('k'), 'refraction', ('delta', 'delete', 'following'))

ea(ctl('w'), 'refraction', ('delta', 'delete', 'backward', 'adjacent', 'class'))
ea(ctl('t'), 'refraction', ('delta', 'delete', 'forward', 'adjacent', 'class'))

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
