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

# Status modifiers used to control actions based on the focused view.
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
control = Mode(('cursor', 'seek/character/pattern', ()))
insert = Mode(('cursor', 'insert/characters', ()))
annotations = Mode(('cursor', 'transition/annotation/void', ()))
relay = Mode(('view', 'dispatch/device/status', ()))

# Dispatch; return control.
for mode in (control, insert):
	# Set of combinations need to be trapped so they can be forwarded.
	a((k_return, *km_all), 'focus/activate')
	for i in range(0, len(km_all)):
		for mods in combinations(km_all, i):
			a((k_return, *mods), 'focus/activate')

	a((k_return, km_meta), 'cursor/substitute/selected/command')
	a((k_return, km_location), 'location/execute/operation')

	a((k_return, km_executing, km_retain), 'prompt/execute/reset')
	a((k_return, km_executing, km_retain, km_control), 'prompt/execute/repeat')
	a((k_return, km_executing, km_retain, km_control, km_shift), 'prompt/execute/close')

	a((k_return, km_executing, km_conceal), 'prompt/execute/close')
	a((k_return, km_executing, km_conceal, km_control), 'prompt/execute/reset')
	a((k_return, km_executing, km_conceal, km_control, km_shift), 'prompt/execute/repeat')

	a(('[M1]'), 'frame/select/absolute')

	a((0x2190), 'view/seek/cell/previous')
	a((0x2191), 'view/seek/line/previous')
	a((0x2192), 'view/seek/cell/next')
	a((0x2193), 'view/seek/line/next')

	a((0x21DF), 'view/seek/line/next/few')
	a((0x21DE), 'view/seek/line/previous/few')
	a((0x21F1), 'view/seek/line/first')
	a((0x21F2), 'view/seek/line/last')

	a((0x21E5), 'cursor/insert/indentation')
	a((0x21E5, km_shift), 'cursor/delete/indentation')
	a((0x21E5, km_meta), 'frame/switch/view/next')
	a((0x21E5, km_shift, km_meta), 'frame/switch/view/previous')

	a((0x21E5, km_void, km_d), 'cursor/insert/indentation/selected')
	a((0x21E5, km_shift, km_d), 'cursor/delete/indentation/selected')

if 'controls':
	mode = control

	a((k_return, km_writing, km_control), 'frame/switch/view/return')
	a((k_return, km_writing, km_shift), 'cursor/seek/void/line/previous')
	a((k_return, km_writing), 'cursor/seek/void/line/next')
	a(('c', km_location, km_control), 'location/reset')
	a(('c', km_executing, km_retain, km_control), 'frame/refocus')
	a(('c', km_executing, km_conceal, km_control), 'prompt/close')
	a(('c', km_writing, km_control), 'annotation/interrupt')

	a((k_space, km_control), 'frame/prompt/host')
	a((k_space, km_shift, km_control), 'frame/prompt/process')

	a(('a'), 'cursor/transition/insert/end-of-field')
	a(('a', km_shift), 'cursor/transition/insert/end-of-line')

	a(('b'), 'cursor/line/break')
	a(('b', km_shift), 'cursor/line/join')

	a(('c'), 'cursor/substitute/selected/characters')
	a(('c', km_shift), 'cursor/substitute/again')
	a(('c', km_control), 'focus/cancel')
	a(('c', km_meta), 'cursor/copy/selected/lines')
	a(('c', km_shift, km_meta), 'cursor/cut/selected/lines')

	a(('d'), 'cursor/seek/field/previous')
	a(('d', km_shift), 'cursor/seek/selected/character/first')

	a(('f'), 'cursor/seek/field/next')
	a(('f', km_shift), 'cursor/seek/selected/character/last')

	a(('g', km_control), 'frame/prompt/seek/absolute')
	a(('g', km_shift, km_control), 'frame/prompt/seek/relative')

	a(('h'), 'cursor/select/line')
	a(('h', km_shift), 'cursor/seek/line/bisection')

	a(('i'), 'cursor/transition/insert')
	a(('i', km_shift), 'cursor/transition/insert/start-of-line')

	a(('j'), 'cursor/seek/line/next')
	a(('j', km_shift), 'cursor/seek/selected/line/last')
	a(('j', km_control), 'cursor/seek/void/line/next')
	a(('j', km_meta), 'frame/switch/view/next')

	a(('k'), 'cursor/seek/line/previous')
	a(('k', km_shift), 'cursor/seek/selected/line/first')
	a(('k', km_control), 'cursor/seek/void/line/previous')
	a(('k', km_meta), 'frame/switch/view/previous')

	a(('l'), 'cursor/select/indentation')
	a(('l', km_shift), 'cursor/select/indentation/level')
	a(('l', km_control), 'frame/open/resource')
	a(('l', km_meta, km_control), 'session/open/log')

	a(('m'), 'cursor/move/selected/lines/ahead')
	a(('m', km_shift), 'cursor/move/selected/lines/behind')
	a(('m', km_control), 'cursor/copy/selected/lines/ahead')
	a(('m', km_control, km_shift), 'cursor/copy/selected/lines/behind')

	a(('n'), 'cursor/seek/match/next')
	a(('n', km_shift), 'cursor/seek/match/previous')
	a(('n', km_shift, km_control), 'cursor/configure/pattern')
	a(('n', km_control), 'frame/prompt/pattern')

	a(('o'), 'cursor/open/ahead')
	a(('o', km_shift), 'cursor/open/behind')
	a(('o', km_control, km_shift), 'cursor/open/first')
	a(('o', km_control), 'cursor/open/last')

	a(('p'), 'cursor/take')
	a(('p', km_shift), 'cursor/place')

	a(('r'), 'cursor/transition/capture/replace')
	a(('r', km_shift), 'cursor/swap/case/character')
	a(('r', km_shift, km_d), 'cursor/swap/case/selected/characters')
	a(('r', km_control), 'frame/prompt/replace')
	a(('r', km_meta), 'view/refresh')

	a(('s'), 'cursor/select/field/series')
	a(('s', km_shift), 'cursor/select/line/characters')
	a(('s', km_control), 'frame/prompt/save')

	a(('v'), 'cursor/transition/annotation/select')
	a(('v', km_shift), 'cursor/annotation/rotate')
	a(('v', km_control), 'cursor/zero/indentation')
	a(('v', km_control, km_d), 'cursor/zero/indentation/selected')
	a(('v', km_meta), 'cursor/paste/after')
	a(('v', km_meta, km_shift), 'cursor/paste/before')

	a(('u'), 'resource/undo')
	a(('u', km_shift), 'resource/redo')

	a(('x'), 'cursor/delete/character/next')
	a(('x', km_void, km_d), 'cursor/delete/selected/characters')
	a(('x', km_shift), 'cursor/delete/character/previous')
	a(('x', km_shift, km_d), 'cursor/delete/column')
	a(('x', km_control, km_d), 'cursor/delete/selected/lines')
	a(('x', km_control), 'cursor/delete/line/next')
	a(('x', km_meta), 'cursor/cut/selected/lines')
	a(('x', km_shift, km_control), 'cursor/delete/line/previous')

	a(('y'), 'cursor/transition/distribution')

	a(('z'), 'cursor/configure/last/selected/line')
	a(('z', km_shift), 'cursor/configure/first/selected/line')

	a((k_space), 'cursor/seek/character/next')
	a((k_space, km_shift), 'cursor/seek/character/previous')
	a((0x2326), 'cursor/seek/character/previous')
	a((0x232B), 'cursor/seek/character/previous')

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
	a(('p'), 'cursor/annotate/directory')

if 'inserts':
	mode = insert

	a((k_return, km_writing), 'cursor/line/break/follow')
	a((k_space, km_shift), 'cursor/insert/escaped-space')

	a(('a', km_control), 'cursor/seek/character/first')
	a(('c', km_control), 'cursor/abort')
	a(('d', km_control), 'cursor/commit')
	a(('e', km_control), 'cursor/seek/character/last')
	a(('f', km_control), 'annotation/select/next')
	a(('f', km_control, km_shift), 'annotation/select/previous')
	a(('g', km_control), 'cursor/insert/annotation')
	a(('k', km_control), 'cursor/delete/following')
	a(('t', km_control), 'cursor/delete/forward/adjacent/class')
	a(('u', km_control), 'cursor/delete/leading')
	a(('v', km_control), 'cursor/transition/capture/insert')
	a(('v', km_control, km_meta), 'cursor/transition/capture/key')
	a(('w', km_control), 'cursor/delete/field/previous')
	a(('x', km_control), 'cursor/delete/character/previous')

	a((0x232B), 'cursor/delete/character/previous')
	a((0x2326), 'cursor/delete/character/previous')

	a((0x2190), 'cursor/seek/character/previous')
	a((0x2191), 'cursor/seek/character/first')
	a((0x2192), 'cursor/seek/character/next')
	a((0x2193), 'cursor/seek/character/last')

del a
