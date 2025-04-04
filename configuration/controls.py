"""
# Key bindings for controlling terminal applications.
"""
from ..elements.types import Mode
from itertools import combinations

k_return = 0x23CE
k_space = 0x2423

km_shift = "Shift"
km_control = "Control"
km_meta = "Meta"
km_void = "None"
km_d = "Distribution"

# Status modifiers used to control actions based on the selected view.
km_location = "Location"
km_writing = "Writing"
km_executing = "Executing"
km_reading = "Reading"
km_retain = "Retained"
km_conceal = "Concealed"
km_all = [km_shift, km_control, km_meta, km_d]

modifiers = {
	"None": ord('-'),
	"Imaginary": 0x2148,
	"Shift": 0x21E7,
	"Control": 0x2303,
	"System": 0x2318,
	"Meta": 0x2325,
	"Hyper": 0x2726,
	"Distribution": 0x0394,

}

status_modifiers = {
	# Status modifiers identifying the status of the focus.
	"Reading": ord('R'),   # Paging
	"Writing": ord('W'),   # Editing
	"Executing": ord('X'), # Prompt
	"Location": ord('L'),

	# Concealment policy on activate.
	"Retained": ord('Z'),
	"Concealed": ord('z'),
}

def a(ks, method, *args):
	global mode

	if isinstance(ks, tuple):
		k, *mods = ks
		smods = [status_modifiers[m] for m in mods if m in status_modifiers]
		smods.sort()
	else:
		k = ks
		mods = ()
		smods = list()

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

	cmods = [modifiers[x] for x in mods if x not in status_modifiers]
	if not cmods:
		ki += '[-'
	else:
		cmods.sort(key=(lambda x: x if x > 0x2000 else 0x6000))
		ki += '['
		ki += ''.join(map(chr, cmods))

	ki += ''.join(map(chr, smods))
	ki += ']'

	if isinstance(method, str):
		itype, action = method.split('/', 1)
	else:
		itype, *action = method
		action = tuple(action)
	mode.assign(ki, itype, action, *args)

# Modes
control = Mode(('cursor', 'move/jump/character', ()))
insert = Mode(('cursor', 'insert/character', ()))
annotations = Mode(('cursor', 'transition/annotation/void', ()))
relay = Mode(('view', 'dispatch/device/status', ()))

# Dispatch; return control.
import sys
for mode in (control, insert):
	# Set of combinations need to be trapped so they can be forwarded.
	a((k_return, *km_all), 'session/activate')
	for i in range(0, len(km_all)):
		for mods in combinations(km_all, i):
			a((k_return, *mods), 'session/activate')

	a((k_return, km_meta), 'cursor/substitute/selected/command')
	a((k_return, km_location), 'session/execute/reset')

	a((k_return, km_executing, km_retain), 'session/execute/reset')
	a((k_return, km_executing, km_retain, km_control), 'session/execute/repeat')
	a((k_return, km_executing, km_retain, km_control, km_shift), 'session/execute/close')

	a((k_return, km_executing, km_conceal), 'session/execute/close')
	a((k_return, km_executing, km_conceal, km_control), 'session/execute/reset')
	a((k_return, km_executing, km_conceal, km_control, km_shift), 'session/execute/repeat')

if 'controls':
	mode = control

	a((k_return, km_writing, km_control), 'frame/view/return')
	a((k_return, km_writing, km_shift), 'cursor/move/backward/line/void')
	a((k_return, km_writing), 'cursor/move/forward/line/void')
	a(('c', km_location, km_control), 'frame/cancel')
	a(('c', km_executing, km_retain, km_control), 'frame/refocus')
	a(('c', km_executing, km_conceal, km_control), 'frame/cancel')

	a((k_space, km_control), 'frame/prepare/command')

	a(('a'), 'cursor/transition/insert/end-of-field')
	a(('a', km_shift), 'cursor/transition/insert/end-of-line')

	a(('b'), 'cursor/line/break')
	a(('b', km_shift), 'cursor/line/join')

	a(('c'), 'cursor/substitute/selected/characters')
	a(('c', km_shift), 'cursor/substitute/again')
	a(('c', km_control), 'session/cancel')
	a(('c', km_meta), 'cursor/copy/selected/lines')
	a(('c', km_shift, km_meta), 'cursor/cut/selected/lines')

	a(('d'), 'cursor/move/backward/field')
	a(('d', km_shift), 'cursor/move/start/character')
	a(('d', km_control), 'cursor/horizontal/query/backward')

	a(('f'), 'cursor/move/forward/field')
	a(('f', km_shift), 'cursor/move/stop/character')
	a(('f', km_control), 'cursor/horizontal/query/forward')

	a(('g', km_control), 'session/seek/element/absolute')
	a(('g', km_shift, km_control), 'session/seek/element/relative')

	a(('h'), 'cursor/select/line')
	a(('h', km_shift), 'cursor/move/bisect/line')

	a(('i'), 'cursor/transition/insert')
	a(('i', km_shift), 'cursor/transition/insert/start-of-line')

	a(('j'), 'cursor/move/forward/line')
	a(('j', km_shift), 'cursor/move/stop/line')
	a(('j', km_control), 'cursor/move/forward/line/void')
	a(('j', km_meta), 'frame/view/next')

	a(('k'), 'cursor/move/backward/line')
	a(('k', km_shift), 'cursor/move/start/line')
	a(('k', km_control), 'cursor/move/backward/line/void')
	a(('k', km_meta), 'frame/view/previous')

	a(('l'), 'cursor/select/indentation')
	a(('l', km_shift), 'cursor/select/indentation/level')
	a(('l', km_control), 'frame/open/resource')
	a(('l', km_meta, km_control), 'session/open/log')

	a(('m'), 'cursor/move/line/selection/ahead')
	a(('m', km_shift), 'cursor/move/line/selection/behind')
	a(('m', km_control), 'cursor/copy/line/selection/ahead')
	a(('m', km_control, km_shift), 'cursor/copy/line/selection/behind')

	a(('n'), 'cursor/find/next/pattern')
	a(('n', km_shift), 'cursor/find/previous/pattern')
	a(('n', km_shift, km_control), 'cursor/configure/find/pattern')
	a(('n', km_control), 'frame/prompt/find')

	a(('o'), 'cursor/open/ahead')
	a(('o', km_shift), 'cursor/open/behind')
	a(('o', km_control, km_shift), 'cursor/open/first')
	a(('o', km_control), 'cursor/open/last')

	a(('p'), 'cursor/take')
	a(('p', km_shift), 'cursor/place')

	a(('r'), 'cursor/transition/capture/replace')
	a(('r', km_shift), 'cursor/swap/case/character')
	a(('r', km_shift, km_d), 'cursor/swap/case/selected/characters')
	a(('r', km_control), 'frame/prompt/rewrite')
	a(('r', km_meta), 'view/refresh')

	a(('s'), 'cursor/select/field/series')
	a(('s', km_shift), 'cursor/select/line/characters')
	a(('s', km_control), 'frame/save/resource')

	a(('v'), 'cursor/transition/annotation/select')
	a(('v', km_shift), 'cursor/annotation/rotate')
	a(('v', km_control), 'cursor/indentation/zero')
	a(('v', km_control, km_d), 'cursor/indentation/zero/selected')
	a(('v', km_meta), 'cursor/paste/after')
	a(('v', km_meta, km_shift), 'cursor/paste/before')

	a(('u'), 'resource/undo')
	a(('u', km_shift), 'resource/redo')

	a(('x'), 'cursor/delete/current/character')
	a(('x', km_void, km_d), 'cursor/delete/selected/characters')
	a(('x', km_shift), 'cursor/delete/preceding/character')
	a(('x', km_shift, km_d), 'cursor/delete/column')
	a(('x', km_control, km_d), 'cursor/delete/selected/lines')
	a(('x', km_control), 'cursor/delete/current/line')
	a(('x', km_meta), 'cursor/cut/selected/lines')
	a(('x', km_shift, km_control), 'cursor/delete/preceding/line')

	a(('y'), 'session/mode/set/distribution')

	a(('z'), 'cursor/move/line/stop')
	a(('z', km_shift), 'cursor/move/line/start')

	a((k_space), 'cursor/move/forward/character')
	a((k_space, km_shift), 'cursor/move/backward/character')
	a((0x2326), 'cursor/move/backward/character')
	a((0x232B), 'cursor/move/backward/character')
	a((0x21E5, km_meta), 'frame/view/next')
	a((0x21E5, km_shift, km_meta), 'frame/view/previous')

	a((0x21E5), 'cursor/indentation/increment')
	a((0x21E5, km_shift), 'cursor/indentation/decrement')
	a((0x21E5, km_void, km_d), 'cursor/indentation/increment/selected')
	a((0x21E5, km_shift, km_d), 'cursor/indentation/decrement/selected')

	a(('[M1]'), 'cursor/select/absolute')

	a((0x2190), 'view/pan/backward')
	a((0x2191), 'view/scroll/backward')
	a((0x2192), 'view/pan/forward')
	a((0x2193), 'view/scroll/forward')

	a((0x21DF), 'view/scroll/forward/third')
	a((0x21DE), 'view/scroll/backward/third')
	a((0x21F1), 'view/scroll/first')
	a((0x21F2), 'view/scroll/last')

if 'annotations':
	mode = annotations

	a(('8'), 'cursor/annotate/codepoint/select/utf-8')
	a(('b'), 'cursor/annotate/integer/select/binary')
	a(('c'), 'cursor/annotate/integer/color/swatch')
	a(('d'), 'cursor/annotate/integer/select/decimal')
	a(('o'), 'cursor/annotate/integer/select/octal')
	a(('s'), 'cursor/annotate/status')
	a(('u'), 'cursor/annotate/integer/select/glyph')
	a(('x'), 'cursor/annotate/integer/select/hexadecimal')

if 'inserts':
	mode = insert
	a((k_return, km_writing), 'cursor/line/break/follow')

	a(('a', km_control), 'cursor/move/first/character')
	a(('c', km_control), 'cursor/abort')
	a(('d', km_control), 'cursor/commit')
	a(('e', km_control), 'cursor/move/last/character')
	a(('f', km_control), 'cursor/annotation/select/next')
	a(('g', km_control), 'cursor/insert/annotation')
	a(('k', km_control), 'cursor/delete/following')
	a(('t', km_control), 'cursor/delete/forward/adjacent/class')
	a(('u', km_control), 'cursor/delete/leading')
	a(('v', km_control), 'cursor/transition/capture/insert')
	a(('v', km_control, km_meta), 'cursor/transition/capture/key')
	a(('w', km_control), 'cursor/delete/preceding/field')
	a(('x', km_control), 'cursor/delete/preceding/character')

	a((0x232B), 'cursor/delete/preceding/character')
	a((0x2326), 'cursor/delete/preceding/character')

	a((0x2190), 'cursor/move/backward/character')
	a((0x2191), 'cursor/move/first/character')
	a((0x2192), 'cursor/move/forward/character')
	a((0x2193), 'cursor/move/last/character')

	a((k_space, km_control), 'cursor/insert/string', ("\x1f",))

	a((0x21E5), 'cursor/indentation/increment')
	a((0x21E5, km_shift), 'cursor/indentation/decrement')

del a
