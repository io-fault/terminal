"""
# Default keyboard mappings.

# [ Properties ]
# /control/
	# Control mode mapping is for navigation and high-level manipulation.
# /insert/
	# Mode used to manage the insertion and removal of characters from fields.
# /capture/
	# Insert the exact character captured.
"""

import codecs
from fault.terminal import events

class Mode(object):
	"""
	# A mapping of user events to application events.

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
	return ('navigation', x, mods)

# Modes
control = Mode(('navigation', ('horizontal', 'jump', 'unit'), ()))
insert = Mode(('delta', ('insert', 'character'), ()))
annotations = Mode(('meta', ('transition', 'annotation', 'void'), ()))

# Shorthands
ca = control.assign
ea = insert.assign
aa = annotations.assign

if 'exits':
	ca(ctl('q'), 'meta', ('session', 'exit'))

ca(lit('j', meta), 'navigation', ('view', 'next', 'refraction'))
ca(lit('k', meta), 'navigation', ('view', 'previous', 'refraction'))
ca(ctl('i', meta), 'navigation', ('session', 'view', 'forward'))
ca(ctl('i', shiftmeta), 'navigation', ('session', 'view', 'backward'))
ca(ctl('l'), 'navigation', ('session', 'load', 'resource'))
ca(ctl('s'), 'navigation', ('session', 'store', 'resource'))
ca(ctl('c'), 'navigation', ('session', 'cancel'))

ca(ctl('g'), 'navigation', ('session', 'seek', 'element', 'absolute'))
ca(lit('g', ctlm), 'navigation', ('session', 'seek', 'element', 'absolute'))
ca(lit('g', ctlm|shift), 'navigation', ('session', 'seek', 'element', 'relative'))

ca(ctl('n'), 'navigation', ('session', 'search', 'resource'))
ca(lit('n', ctlm), 'navigation', ('session', 'search', 'resource'))
ca(lit('n', ctlm|shift), 'navigation', ('find', 'selected'))
ca(lit('n'), 'navigation', ('find', 'next'))
ca(lit('N'), 'navigation', ('find', 'previous'))

ca(lit('r'), 'meta', ('transition', 'capture', 'replace'))
ea(ctl('v'), 'meta', ('transition', 'capture', 'insert'))
ca(ctl('m', ctlm), 'meta', ('view', 'refresh'))
ca(ctl('m', shift), 'navigation', ('view', 'return'))
ca(ctl('r'), 'navigation', ('session', 'rewrite', 'elements'))
ca(lit('r', ctlm), 'navigation', ('session', 'rewrite', 'elements'))

if 'insert-transitions':
	ca(lit('O'), 'delta', ('open', 'behind'))
	ca(lit('o'), 'delta', ('open', 'ahead'))

	# Session control.
	ca(ctl('z'), 'meta', ('session', 'suspend'))
	ea(ctl('z'), 'meta', ('session', 'suspend'))

	# Event control.
	ca(lit('i'), 'meta', ('transition',))
	ca(lit('a'), 'meta', ('transition', 'end-of-field'))
	ca(lit('I'), 'meta', ('transition', 'start-of-line'))
	ca(lit('A'), 'meta', ('transition', 'end-of-line'))

	# Distribution of commands across the vertical range.
	ca(lit('y'), 'meta', ('select', 'distributed', 'operation'))

if 'transactions-management':
	ea(ctl('c'), 'transaction', ('abort',)) # Default SIGINT.
	ea(ctl('d'), 'transaction', ('commit',)) # Default EOF.
	ca(lit('u'), 'transaction', ('undo',))
	ca(lit('U'), 'transaction', ('redo',))

if 'cache-operations':
	ca(lit('c', meta), 'delta', ('copy',))
	ca(lit('c', shiftmeta), 'delta', ('cut',))
	ca(lit('ξ'), 'delta', ('cut',))
	ca(lit('p'), 'delta', ('paste', 'after',))
	ca(lit('P'), 'delta', ('paste', 'before',))

if 'activations':
	# Refractions need to respond differently here, so a generic term is used.
	# Notably, the location area needs to perform an open or switch operation
	# when return is pressed regardless of the mode.
	ca(ctl('m'), 'navigation', ('activate',))
	ea(ctl('m'), 'navigation', ('activate',))

if 'annotations':
	ea(ctl('g'), 'delta', ('insert', 'annotation'))
	ea(ctl('f'), 'meta', ('query',))
	ca(lit('v'), 'meta', ('transition', 'annotations', 'select'))
	ca(lit('V'), 'meta', ('annotation', 'rotate'))
	aa(lit('s'), 'meta', ('status',))
	aa(lit('c'), 'meta', ('integer', 'color', 'swatch'))
	aa(lit('x'), 'meta', ('integer', 'select', 'hexadecimal'))
	aa(lit('o'), 'meta', ('integer', 'select', 'octal'))
	aa(lit('b'), 'meta', ('integer', 'select', 'binary'))
	aa(lit('d'), 'meta', ('integer', 'select', 'decimal'))
	aa(lit('8'), 'meta', ('codepoint', 'select', 'utf-8'))

ca(lit('f'), 'navigation', ('horizontal', 'forward'))
ca(lit('d'), 'navigation', ('horizontal', 'backward'))
ca(lit('F'), 'navigation', ('horizontal', 'stop'))
ca(lit('D'), 'navigation', ('horizontal', 'start'))
ca(ctl('f'), 'navigation', ('horizontal', 'query', 'forward'))
ca(ctl('d'), 'navigation', ('horizontal', 'query', 'backward'))
ca(ctl(' '), 'navigation', ('horizontal', 'forward', 'unit'))
ca(ctl('?'), 'navigation', ('horizontal', 'backward', 'unit'))
ca(ctl('h'), 'navigation', ('horizontal', 'backward', 'unit'))

# Navigation in insert.
ea(nav('left'), 'navigation', ('horizontal', 'backward', 'unit'))
ea(nav('right'), 'navigation', ('horizontal', 'forward', 'unit'))
ea(nav('up'), 'navigation', ('horizontal', 'backward', 'beginning'))
ea(nav('down'), 'navigation', ('horizontal', 'forward', 'end'))
ea(ctl('a'), 'navigation', ('horizontal', 'backward', 'beginning'))
ea(ctl('e'), 'navigation', ('horizontal', 'forward', 'end'))

# Cursor range controls.
ca(lit('z'), 'navigation', ('vertical', 'place', 'stop',))
ca(lit('Z'), 'navigation', ('vertical', 'place', 'start',))
ca(lit('H'), 'navigation', ('vertical', 'place', 'center'))
ca(lit('s'), 'navigation', ('horizontal', 'select', 'series',))
ca(lit('S'), 'navigation', ('horizontal', 'select', 'line'))
ca(lit('L'), 'navigation', ('vertical', 'select', 'indentation', 'level'))
ca(lit('l'), 'navigation', ('vertical', 'select', 'indentation'))
ca(lit('h'), 'navigation', ('vertical', 'select', 'line'))
ca(lit('e'), 'navigation', ('vertical', 'sections'))
ca(lit('E'), 'navigation', ('vertical', 'paging'))

ca(lit('j'), 'navigation', ('vertical', 'forward', 'unit'))
ca(lit('k'), 'navigation', ('vertical', 'backward', 'unit'))
ca(lit('J'), 'navigation', ('vertical', 'stop'))
ca(lit('K'), 'navigation', ('vertical', 'start'))
ca(ctl('j'), 'navigation', ('vertical', 'void', 'forward'))
ca(ctl('k'), 'navigation', ('vertical', 'void', 'backward'))

ca(nav('left'), 'navigation', ('view', 'horizontal', 'backward'))
ca(nav('right'), 'navigation', ('view', 'horizontal', 'forward'))
ca(nav('down'), 'navigation', ('view', 'vertical', 'forward'))
ca(nav('up'), 'navigation', ('view', 'vertical', 'backward'))

ca(nav('page-down'), 'navigation', ('view', 'vertical', 'forward', 'third'))
ca(nav('page-up'), 'navigation', ('view', 'vertical', 'backward', 'third'))
ca(nav('home'), 'navigation', ('view', 'vertical', 'start'))
ca(nav('end'), 'navigation', ('view', 'vertical', 'stop'))

ca(lit('c'), 'delta', ('horizontal', 'substitute', 'range'))
ca(lit('C'), 'delta', ('horizontal', 'substitute', 'again'))

ca(lit('x'), 'delta', ('delete', 'unit', 'current'))
ca(lit('X'), 'delta', ('delete', 'unit', 'former'))
ca(ctl('x'), 'delta', ('delete', 'element', 'current'))
ca(lit('x', shift|ctlm), 'delta', ('delete', 'element', 'former'))

ca(lit('M'), 'delta', ('move', 'range', 'behind'))
ca(lit('m'), 'delta', ('move', 'range', 'ahead'))

ca(lit('b'), 'delta', ('line', 'break',))
ca(lit('B'), 'delta', ('line', 'join',))

ca(ctl('i'), 'delta', ('indentation', 'increment'))
ca(ctl('i', shift), 'delta', ('indentation', 'decrement'))
ca(ctl('v'), 'delta', ('indentation', 'zero'))
ea(ctl('i'), 'delta', ('indentation', 'increment'))
ea(ctl('i', shift), 'delta', ('indentation', 'decrement'))

ea(ctl(' ', ctlm), 'delta', ('insert', 'string',), ("\x1f",))
ca(ctl(' ', ctlm), 'navigation', ('horizontal', 'jump', 'string',), ("\x1f",))

ea(ctl('?'), 'delta', ('delete', 'unit', 'former'))
ea(ctl('h'), 'delta', ('delete', 'unit', 'former'))
ea(ctl('x'), 'delta', ('delete', 'unit', 'current'))

ea(ctl('u'), 'delta', ('delete', 'leading'))
ea(ctl('k'), 'delta', ('delete', 'following'))

ea(ctl('w'), 'delta', ('delete', 'backward', 'adjacent', 'class'))
ea(ctl('t'), 'delta', ('delete', 'forward', 'adjacent', 'class'))

del ea, ca, nav, ctl, lit, shift, kmeta

standard = {
	'control': control,
	'insert': insert,
	'annotations': annotations,
	'capture-insert': Mode(('delta', ('insert', 'capture'), ())),
	'capture-replace': Mode(('delta', ('replace', 'capture'), ())),
}

# Translations for `distributed` qualification.
# Maps certain operations to vertical or horizontal mapped operations.
distributions = {
	('delta', x): ('delta', y)
	for x, y in [
		(('delete', 'unit', 'current'), ('delete', 'horizontal', 'range')),
		(('delete', 'unit', 'former'), ('delete', 'vertical', 'column')),
		(('delete', 'element', 'current'), ('delete', 'vertical', 'range')),
		(('delete', 'element', 'former'), ('delete', 'vertical', 'range')),

		(('indentation', 'increment'), ('indentation', 'increment', 'range')),
		(('indentation', 'decrement'), ('indentation', 'decrement', 'range')),
		(('indentation', 'zero'), ('indentation', 'zero', 'range')),
	]
}

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
	# /redirects/
		# The event translation that occurs when the selection state
		# is under a qualified mode.
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
		self.redirections = {}
		self.qualification = None
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

	def qualify(self, qid):
		"""
		# Update the qualification.
		"""

		self.qualification = qid

	def event(self, key):
		"""
		# Look up the event using the currently selected mapping.
		"""

		return (self.current[0], self.current[1].event(key))

	def redirect(self, event):
		prefix = event[:2]
		re = self.redirections[self.qualification].get(prefix, prefix)
		return re + (event[2],)

	def interpret(self, event):
		"""
		# Route the event to the target given the current processing state.
		"""

		if event.type in {'focus', 'mouse', 'scroll', 'data', 'paste'}:
			if event.type == 'mouse':
				point, key_id, delay = event.identity
				return (None, ('navigation', ('select', 'absolute'), ()))
			elif event.type == 'scroll':
				sq, sd = event.identity[1:]
				if sd == 0:
					a = 'vertical'
				elif sd == 2:
					a = 'horizontal'
				if sq < 0:
					d = 'backward'
				else:
					d = 'forward'
				return (None, ('navigation', ('view', a, d), (abs(sq),)))
			elif event.type == 'data':
				self.data.append(event.string)
				return (None, ('meta', ('ineffective',), ()))
			elif event.type == 'paste':
				if event.identity == 'start':
					self.data = list()
					return (None, ('meta', ('ineffective',), ()))
				elif event.identity == 'stop':
					op = (None, ('delta', ('insert', 'data'), (self.data,)))
					self.data = None
					return op
				else:
					assert False # Unknown paste event.
			elif event.type == 'focus':
				if event.identity == 'in':
					return (None, ('meta', ('terminal', 'focus', 'acquire'), ()))
				elif event.identity == 'out':
					return (None, ('meta', ('terminal', 'focus', 'release'), ()))

		mapping, operation = self.event(event)
		if operation is None:
			return (None, ('meta', ('ineffective',), ()))
		if self.qualification is not None:
			operation = self.redirect(operation)
			self.qualification = None

		return (mapping, operation)

def merge(events):
	"""
	# Combine scroll events so that fewer scroll operations will be performed.
	"""
	deletions = []
	scroll = None
	for i, c in enumerate(events):
		if c.type == 'scroll':
			if scroll is not None and scroll[1].identity[0] == c.identity[0]:
				# scroll on identical cell, merge.
				eid = (
					c.identity[0],
					c.identity[1] + scroll[1].identity[1],
				) + c.identity[2:]
				deletions.append(scroll[0])
				scroll = (i, c.__class__((c[0], c[1], eid, *c[3:])))
				events[i] = scroll[1]
			else:
				scroll = (i, c)
		elif scroll is not None:
			# Presume distinct.
			scroll = None

	# Remove merged events.
	for i in reversed(deletions):
		del events[i]

	return events

def input_line_state(encoding='utf-8', error='surrogateescape'):
	state = codecs.getincrementaldecoder(encoding)(error)
	decode = state.decode
	parse = events.parser().send

	datav = (yield None)
	while True:
		chars = parse((decode(b''.join(datav)), 0))
		datav = (yield merge(chars))

if __name__ == '__main__':
	kb = Selection(standard)
	kb.set('insert')
	import os, sys, time
	from fault.terminal import matrix, control
	from fault.time.system import elapsed
	tty, pre, res = control.setup()
	S = matrix.Screen(matrix.utf8_terminal_type)
	ctx = matrix.Context(matrix.utf8_terminal_type)
	ctx.context_set_position((0, 0))
	w, h = tty.get_window_dimensions()
	ctx.context_set_dimensions((w, h))
	sys.stdout.buffer.write(S.store_cursor_location())
	pre()
	try:
		ils = input_line_state(elapsed)
		ils.send(None)
		while True:
			raw = os.read(sys.stdin.fileno(), 1024)
			ts, events = ils.send([raw])
			for event in events:
				xev = kb.interpret(event)
				print(repr(xev)+'\r')
	finally:
		res()
		sys.stdout.buffer.write(S.restore_cursor_location())
