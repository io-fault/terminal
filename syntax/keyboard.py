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
from .ia.types import Mode, Selection

km_shift = "Shift"
km_control = "Control"
km_meta = "Meta"

modifiers = {
	"Imaginary": 0x2148,
	"Shift": 0x21E7,
	"Control": 0x2303,
	"System": 0x2318,
	"Meta": 0x2325,
	"Hyper": 0x2726,
}

def a(ks, *massign):
	global mode

	if isinstance(ks, tuple):
		k, *mods = ks
	else:
		k = ks
		mods = ()

	if isinstance(k, int):
		if k >= 0:
			k = chr(k)
		else:
			k = str(k)

	if k[0:1] + k[-1:] in {'()', '[]'}:
		# Application Instruction
		ki = k
	else:
		ki = f"[{k.upper()}]"

	if mods:
		mods = [modifiers[x] for x in mods]
		mods.sort()
		ki += '['
		ki += ''.join(map(chr, mods))
		ki += ']'
	mode.assign(ki, *massign)

# Modes
control = Mode(('navigation', ('horizontal', 'jump', 'unit'), ()))
insert = Mode(('delta', ('insert', 'character'), ()))
annotations = Mode(('meta', ('transition', 'annotation', 'void'), ()))

k_return = 0x23CE

# Return Keystrokes
for mode in (control, insert):
	a((k_return), 'meta', ('activate',))
	a((k_return, km_control), 'meta', ('activate', 'continue'))
	a((k_return, km_meta), 'meta', ('elements', 'dispatch'))
	a((k_return, km_shift), 'navigation', ('view', 'return'))

if 'controls':
	mode = control

	a(('r', km_meta), 'meta', ('view', 'refresh'))
	a((0x2423, km_control), 'meta', ('prepare', 'command'))

	a(('a'), 'meta', ('transition', 'insert', 'end-of-field'))
	a(('a', km_shift), 'meta', ('transition', 'insert', 'end-of-line'))

	a(('b'), 'delta', ('line', 'break',))
	a(('b', km_shift), 'delta', ('line', 'join',))

	a(('c'), 'delta', ('horizontal', 'substitute', 'range'))
	a(('c', km_shift), 'delta', ('horizontal', 'substitute', 'again'))
	a(('c', km_control), 'session', ('cancel',))
	a(('c', km_meta), 'delta', ('copy',))
	a(('c', km_shift, km_meta), 'delta', ('cut',))

	a(('d'), 'navigation', ('horizontal', 'backward'))
	a(('d', km_shift), 'navigation', ('horizontal', 'start'))
	a(('d', km_control), 'navigation', ('horizontal', 'query', 'backward'))

	a(('e'), 'navigation', ('vertical', 'sections'))
	a(('e', km_shift), 'navigation', ('vertical', 'paging'))

	a(('f'), 'navigation', ('horizontal', 'forward'))
	a(('f', km_shift), 'navigation', ('horizontal', 'stop'))
	a(('f', km_control), 'navigation', ('horizontal', 'query', 'forward'))

	a(('g', km_control), 'navigation', ('session', 'seek', 'element', 'absolute'))
	a(('g', km_shift, km_control), 'navigation', ('session', 'seek', 'element', 'relative'))

	a(('h'), 'navigation', ('vertical', 'select', 'line'))
	a(('h', km_shift), 'navigation', ('vertical', 'place', 'center'))

	a(('i'), 'meta', ('transition', 'insert', 'cursor'))
	a(('i', km_shift), 'meta', ('transition', 'insert', 'start-of-line'))

	a(('j'), 'navigation', ('vertical', 'forward', 'unit'))
	a(('j', km_shift), 'navigation', ('vertical', 'stop'))
	a(('j', km_control), 'navigation', ('vertical', 'void', 'forward'))
	a(('j', km_meta), 'navigation', ('view', 'next', 'refraction'))

	a(('k'), 'navigation', ('vertical', 'backward', 'unit'))
	a(('k', km_shift), 'navigation', ('vertical', 'start'))
	a(('k', km_control), 'navigation', ('vertical', 'void', 'backward'))
	a(('k', km_meta), 'navigation', ('view', 'previous', 'refraction'))

	a(('l'), 'navigation', ('vertical', 'select', 'indentation'))
	a(('l', km_shift), 'navigation', ('vertical', 'select', 'indentation', 'level'))
	a(('l', km_control), 'session', ('resource', 'relocate'))

	a(('m'), 'delta', ('move', 'range', 'ahead'))
	a(('m', km_shift), 'delta', ('move', 'range', 'behind'))
	a(('m', km_control), 'delta', ('copy', 'range', 'ahead'))
	a(('m', km_control, km_shift), 'delta', ('copy', 'range', 'behind'))

	a(('n'), 'navigation', ('find', 'next'))
	a(('n', km_shift), 'navigation', ('find', 'previous'))
	a(('n', km_control), 'navigation', ('find', 'configure'))
	a(('n', km_shift, km_control), 'navigation', ('find', 'configure', 'selected'))

	a(('o'), 'delta', ('open', 'ahead'))
	a(('o', km_shift), 'delta', ('open', 'behind'))
	a(('o', km_control, km_shift), 'delta', ('open', 'first'))
	a(('o', km_control), 'delta', ('open', 'last'))

	a(('p'), 'delta', ('take',))
	a(('p', km_shift), 'delta', ('place',))

	a(('r'), 'meta', ('transition', 'capture', 'replace'))
	a(('r', km_shift), 'delta', ('character', 'swap', 'case'))
	a(('r', km_control), 'navigation', ('session', 'rewrite', 'elements'))

	a(('s'), 'navigation', ('horizontal', 'select', 'series',))
	a(('s', km_shift), 'navigation', ('horizontal', 'select', 'line'))
	a(('s', km_control), 'session', ('resource', 'save'))

	a(('v'), 'meta', ('transition', 'annotations', 'select'))
	a(('v', km_shift), 'meta', ('annotation', 'rotate'))
	a(('v', km_control), 'delta', ('indentation', 'zero'))
	a(('v', km_meta), 'delta', ('paste', 'before'))

	a(('u'), 'transaction', ('undo',))
	a(('u', km_shift), 'transaction', ('redo',))

	a(('x'), 'delta', ('delete', 'unit', 'current'))
	a(('x', km_shift), 'delta', ('delete', 'unit', 'former'))
	a(('x', km_control), 'delta', ('delete', 'element', 'current'))
	a(('x', km_meta), 'delta', ('cut',))
	a(('x', km_shift, km_control), 'delta', ('delete', 'element', 'former'))

	a(('y'), 'meta', ('select', 'distributed', 'operation'))

	a(('z'), 'navigation', ('vertical', 'place', 'stop',))
	a(('z', km_shift), 'navigation', ('vertical', 'place', 'start',))

	a((0x2423), 'navigation', ('horizontal', 'forward', 'unit'))
	a((0x2326), 'navigation', ('horizontal', 'backward', 'unit')) # Delete
	a((0x232B), 'navigation', ('horizontal', 'backward', 'unit')) # Backsapce
	a((0x21E5, km_meta), 'navigation', ('session', 'view', 'forward'))
	a((0x21E5, km_shift, km_meta), 'navigation', ('session', 'view', 'backward'))

	a((0x21E5), 'delta', ('indentation', 'increment'))
	a((0x21E5, km_shift), 'delta', ('indentation', 'decrement'))

	a(('[M1]'), 'navigation', ('select', 'absolute'))
	a(('(view/scroll)'), 'navigation', ('view', 'vertical', 'scroll'))
	a(('(view/scroll)', km_shift), 'navigation', ('view', 'vertical', 'scroll'))
	a(('(view/pan)'), 'navigation', ('view', 'horizontal', 'pan'))
	a(('(view/pan)', km_shift), 'navigation', ('view', 'horizontal', 'pan'))

	a((0x2190), 'navigation', ('view', 'horizontal', 'backward'))
	a((0x2191), 'navigation', ('view', 'vertical', 'backward'))
	a((0x2192), 'navigation', ('view', 'horizontal', 'forward'))
	a((0x2193), 'navigation', ('view', 'vertical', 'forward'))

	a((0x21DF), 'navigation', ('view', 'vertical', 'forward', 'third')) # Page Down
	a((0x21DE), 'navigation', ('view', 'vertical', 'backward', 'third')) # Page Up
	a((0x21F1), 'navigation', ('view', 'vertical', 'start')) # Home
	a((0x21F2), 'navigation', ('view', 'vertical', 'stop')) # End

if 'annotations':
	mode = annotations

	a(('8'), 'meta', ('codepoint', 'select', 'utf-8'))
	a(('b'), 'meta', ('integer', 'select', 'binary'))
	a(('c'), 'meta', ('integer', 'color', 'swatch'))
	a(('d'), 'meta', ('integer', 'select', 'decimal'))
	a(('o'), 'meta', ('integer', 'select', 'octal'))
	a(('s'), 'meta', ('status',))
	a(('u'), 'meta', ('integer', 'select', 'glyph'))
	a(('x'), 'meta', ('integer', 'select', 'hexadecimal'))

if 'inserts':
	mode = insert

	a(('a', km_control), 'navigation', ('horizontal', 'backward', 'beginning'))
	a(('c', km_control), 'transaction', ('abort',)) # Default SIGINT.
	a(('d', km_control), 'transaction', ('commit',)) # Default EOF.
	a(('e', km_control), 'navigation', ('horizontal', 'forward', 'end'))
	a(('f', km_control), 'meta', ('query',))
	a(('g', km_control), 'delta', ('insert', 'annotation'))
	a(('k', km_control), 'delta', ('delete', 'following'))
	a(('t', km_control), 'delta', ('delete', 'forward', 'adjacent', 'class'))
	a(('u', km_control), 'delta', ('delete', 'leading'))
	a(('v', km_control), 'meta', ('transition', 'capture', 'insert'))
	a(('v', km_control, km_meta), 'meta', ('transition', 'capture', 'key'))
	a(('w', km_control), 'delta', ('delete', 'backward', 'adjacent', 'class'))
	a(('x', km_control), 'delta', ('delete', 'unit', 'current'))

	a((0x232B), 'delta', ('delete', 'unit', 'former'))
	a((0x2326), 'delta', ('delete', 'unit', 'former'))

	a((0x2190), 'navigation', ('horizontal', 'backward', 'unit'))
	a((0x2191), 'navigation', ('horizontal', 'backward', 'beginning'))
	a((0x2192), 'navigation', ('horizontal', 'forward', 'unit'))
	a((0x2193), 'navigation', ('horizontal', 'forward', 'end'))

	a((0x2423, km_control), 'delta', ('insert', 'string',), ("\x1f",))

	a((0x21E5), 'delta', ('indentation', 'increment'))
	a((0x21E5, km_shift), 'delta', ('indentation', 'decrement'))

del a

default = {
	'control': control,
	'insert': insert,
	'annotations': annotations,
	'capture-key': Mode(('delta', ('insert', 'capture', 'key'), ())),
	'capture-insert': Mode(('delta', ('insert', 'capture'), ())),
	'capture-replace': Mode(('delta', ('replace', 'capture'), ())),
}

# Translations for `distributed` qualification.
# Maps certain operations to vertical or horizontal mapped operations.
distributions = {
	('delta', x): ('delta', y)
	for x, y in [
		(('character', 'swap', 'case'), ('horizontal', 'swap', 'case')),
		(('delete', 'unit', 'current'), ('delete', 'horizontal', 'range')),
		(('delete', 'unit', 'former'), ('delete', 'vertical', 'column')),
		(('delete', 'element', 'current'), ('delete', 'vertical', 'range')),
		(('delete', 'element', 'former'), ('delete', 'vertical', 'range')),

		(('indentation', 'increment'), ('indentation', 'increment', 'range')),
		(('indentation', 'decrement'), ('indentation', 'decrement', 'range')),
		(('indentation', 'zero'), ('indentation', 'zero', 'range')),
	]
}
