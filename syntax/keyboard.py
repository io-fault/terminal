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

km_shift = (1 << 1)
km_control = (1 << 2)
km_meta = (1 << 3)

def lit(x, mods=0):
	return (mods, x if isinstance(x, int) else ord(x.upper()))

# Modes
control = Mode(('navigation', ('horizontal', 'jump', 'unit'), ()))
insert = Mode(('delta', ('insert', 'character'), ()))
annotations = Mode(('meta', ('transition', 'annotation', 'void'), ()))

# Shorthands
ca = control.assign
ea = insert.assign
aa = annotations.assign

if 'exits':
	ca(lit('q', km_control), 'meta', ('session', 'exit'))

ca(lit('j', km_meta), 'navigation', ('view', 'next', 'refraction'))
ca(lit('k', km_meta), 'navigation', ('view', 'previous', 'refraction'))
ca(lit(0x21E5, km_meta), 'navigation', ('session', 'view', 'forward'))
ca(lit(0x21E5, km_shift|km_meta), 'navigation', ('session', 'view', 'backward'))
ca(lit('l', km_control), 'navigation', ('session', 'load', 'resource'))
ca(lit('s', km_control), 'navigation', ('session', 'store', 'resource'))
ca(lit('c', km_control), 'navigation', ('session', 'cancel'))

ca(lit('g', km_control), 'navigation', ('session', 'seek', 'element', 'absolute'))
ca(lit('g', km_control|km_shift), 'navigation', ('session', 'seek', 'element', 'relative'))

ca(lit('n', km_control), 'navigation', ('session', 'search', 'resource'))
ca(lit('n', km_control|km_shift), 'navigation', ('find', 'selected'))
ca(lit('n'), 'navigation', ('find', 'next'))
ca(lit('n', km_shift), 'navigation', ('find', 'previous'))

ca(lit('r'), 'meta', ('transition', 'capture', 'replace'))
ea(lit('v', km_control), 'meta', ('transition', 'capture', 'insert'))
ca(lit(0x23CE, km_control), 'meta', ('view', 'refresh'))
ca(lit(0x23CE, km_shift), 'navigation', ('view', 'return'))
ca(lit('r', km_control), 'navigation', ('session', 'rewrite', 'elements'))

if 'insert-transitions':
	ca(lit('o', km_shift), 'delta', ('open', 'behind'))
	ca(lit('o'), 'delta', ('open', 'ahead'))

	# Event control.
	ca(lit('i'), 'meta', ('transition',))
	ca(lit('a'), 'meta', ('transition', 'end-of-field'))
	ca(lit('i', km_shift), 'meta', ('transition', 'start-of-line'))
	ca(lit('a', km_shift), 'meta', ('transition', 'end-of-line'))

	# Distribution of commands across the vertical range.
	ca(lit('y'), 'meta', ('select', 'distributed', 'operation'))

if 'transactions-management':
	ea(lit('c', km_control), 'transaction', ('abort',)) # Default SIGINT.
	ea(lit('d', km_control), 'transaction', ('commit',)) # Default EOF.
	ca(lit('u'), 'transaction', ('undo',))
	ca(lit('u', km_shift), 'transaction', ('redo',))

if 'cache-operations':
	ca(lit('c', km_meta), 'delta', ('copy',))
	ca(lit('c', km_shift|km_meta), 'delta', ('cut',))
	ca(lit('ξ'), 'delta', ('cut',))
	ca(lit('p'), 'delta', ('paste', 'after',))
	ca(lit('p', km_shift), 'delta', ('paste', 'before',))

if 'activations':
	# Refractions need to respond differently here, so a generic term is used.
	# Notably, the location area needs to perform an open or switch operation
	# when return is pressed regardless of the mode.
	ca(lit(0x23CE), 'navigation', ('activate',))
	ea(lit(0x23CE), 'navigation', ('activate',))

if 'annotations':
	ea(lit('g', km_control), 'delta', ('insert', 'annotation'))
	ea(lit('f', km_control), 'meta', ('query',))
	ca(lit('v'), 'meta', ('transition', 'annotations', 'select'))
	ca(lit('v', km_shift), 'meta', ('annotation', 'rotate'))
	aa(lit('s'), 'meta', ('status',))
	aa(lit('c'), 'meta', ('integer', 'color', 'swatch'))
	aa(lit('x'), 'meta', ('integer', 'select', 'hexadecimal'))
	aa(lit('o'), 'meta', ('integer', 'select', 'octal'))
	aa(lit('b'), 'meta', ('integer', 'select', 'binary'))
	aa(lit('d'), 'meta', ('integer', 'select', 'decimal'))
	aa(lit('u'), 'meta', ('integer', 'select', 'glyph'))
	aa(lit('8'), 'meta', ('codepoint', 'select', 'utf-8'))

ca(lit('f'), 'navigation', ('horizontal', 'forward'))
ca(lit('d'), 'navigation', ('horizontal', 'backward'))
ca(lit('f', km_shift), 'navigation', ('horizontal', 'stop'))
ca(lit('d', km_shift), 'navigation', ('horizontal', 'start'))
ca(lit('f', km_control), 'navigation', ('horizontal', 'query', 'forward'))
ca(lit('d', km_control), 'navigation', ('horizontal', 'query', 'backward'))
ca(lit(0x2423), 'navigation', ('horizontal', 'forward', 'unit'))

# Delete
ea(lit(0x2326), 'delta', ('delete', 'unit', 'former'))
ca(lit(0x2326), 'navigation', ('horizontal', 'backward', 'unit'))
# Backspace
ea(lit(0x232B), 'delta', ('delete', 'unit', 'former'))
ca(lit(0x232B), 'navigation', ('horizontal', 'backward', 'unit'))

ca(lit(-2817), 'navigation', ('select', 'absolute'))
ca(lit(-12), 'navigation', ('view', 'vertical', 'scroll'))
ca(lit(-13), 'navigation', ('view', 'horizontal', 'pan'))
ca(lit(-12, km_shift), 'navigation', ('view', 'vertical', 'scroll'))
ca(lit(-13, km_shift), 'navigation', ('view', 'horizontal', 'pan'))

ca(lit(0x2190), 'navigation', ('view', 'horizontal', 'backward'))
ea(lit(0x2190), 'navigation', ('horizontal', 'backward', 'unit'))
ca(lit(0x2191), 'navigation', ('view', 'vertical', 'backward'))
ea(lit(0x2191), 'navigation', ('horizontal', 'backward', 'beginning'))
ca(lit(0x2192), 'navigation', ('view', 'horizontal', 'forward'))
ea(lit(0x2192), 'navigation', ('horizontal', 'forward', 'unit'))
ca(lit(0x2193), 'navigation', ('view', 'vertical', 'forward'))
ea(lit(0x2193), 'navigation', ('horizontal', 'forward', 'end'))

ca(lit(0x21DF), 'navigation', ('view', 'vertical', 'forward', 'third')) # Page Down
ca(lit(0x21DE), 'navigation', ('view', 'vertical', 'backward', 'third')) # Page Up
ca(lit(0x21F1), 'navigation', ('view', 'vertical', 'start')) # Home
ca(lit(0x21F2), 'navigation', ('view', 'vertical', 'stop')) # End

ea(lit('a', km_control), 'navigation', ('horizontal', 'backward', 'beginning'))
ea(lit('e', km_control), 'navigation', ('horizontal', 'forward', 'end'))

# Cursor range controls.
ca(lit('z'), 'navigation', ('vertical', 'place', 'stop',))
ca(lit('z', km_shift), 'navigation', ('vertical', 'place', 'start',))
ca(lit('h', km_shift), 'navigation', ('vertical', 'place', 'center'))
ca(lit('s'), 'navigation', ('horizontal', 'select', 'series',))
ca(lit('s', km_shift), 'navigation', ('horizontal', 'select', 'line'))
ca(lit('l', km_shift), 'navigation', ('vertical', 'select', 'indentation', 'level'))
ca(lit('l'), 'navigation', ('vertical', 'select', 'indentation'))
ca(lit('h'), 'navigation', ('vertical', 'select', 'line'))
ca(lit('e'), 'navigation', ('vertical', 'sections'))
ca(lit('e', km_shift), 'navigation', ('vertical', 'paging'))

ca(lit('j'), 'navigation', ('vertical', 'forward', 'unit'))
ca(lit('k'), 'navigation', ('vertical', 'backward', 'unit'))
ca(lit('j', km_shift), 'navigation', ('vertical', 'stop'))
ca(lit('k', km_shift), 'navigation', ('vertical', 'start'))
ca(lit('j', km_control), 'navigation', ('vertical', 'void', 'forward'))
ca(lit('k', km_control), 'navigation', ('vertical', 'void', 'backward'))

ca(lit('c'), 'delta', ('horizontal', 'substitute', 'range'))
ca(lit('c', km_shift), 'delta', ('horizontal', 'substitute', 'again'))

ca(lit('x'), 'delta', ('delete', 'unit', 'current'))
ca(lit('x', km_shift), 'delta', ('delete', 'unit', 'former'))
ca(lit('x', km_control), 'delta', ('delete', 'element', 'current'))
ca(lit('x', km_shift|km_control), 'delta', ('delete', 'element', 'former'))

ca(lit('m', km_shift), 'delta', ('move', 'range', 'behind'))
ca(lit('m'), 'delta', ('move', 'range', 'ahead'))

ca(lit('b'), 'delta', ('line', 'break',))
ca(lit('b', km_shift), 'delta', ('line', 'join',))

ca(lit(0x21E5), 'delta', ('indentation', 'increment'))
ca(lit(0x21E5, km_shift), 'delta', ('indentation', 'decrement'))
ca(lit('v', km_control), 'delta', ('indentation', 'zero'))
ea(lit(0x21E5), 'delta', ('indentation', 'increment'))
ea(lit(0x21E5, km_shift), 'delta', ('indentation', 'decrement'))

ea(lit(0x2423, km_control), 'delta', ('insert', 'string',), ("\x1f",))
ca(lit(0x2423, km_control), 'navigation', ('horizontal', 'jump', 'string',), ("\x1f",))

ea(lit('x', km_control), 'delta', ('delete', 'unit', 'current'))

ea(lit('u', km_control), 'delta', ('delete', 'leading'))
ea(lit('k', km_control), 'delta', ('delete', 'following'))

ea(lit('w', km_control), 'delta', ('delete', 'backward', 'adjacent', 'class'))
ea(lit('t', km_control), 'delta', ('delete', 'forward', 'adjacent', 'class'))

del ea, ca, lit

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

		if False in {'focus', 'mouse', 'scroll', 'data', 'paste'}:
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
