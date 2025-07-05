"""
# Limited terminal escape interpreter for displaying SGR CSI formatted text.

# [ Elements ]
# /rsts/
	# SGR codes that clear attributes.
# /sets/
	# SGR codes that set attributes.
# /tty_16_color_names/
	# Sequence of color names used by legacy terminals.
# /text_colors_16/
	# Mapping of SGR codes for bright and normal text colors to their color names.
# /cell_colors_16/
	# Mapping of SGR codes for bright and normal cell colors to their color names.
# /brights/
	# Set of SGR codes identifying bright colors; cell or text.
# /csi/
	# The Control Sequence Introducer used to recognize formatting controls.
# /osc/
	# The Operating System Command code.
# /st/
	# The String Terminator. Used to identify the end of a hidden OSC.
"""
import functools
import itertools

rsts = {
	'22': {'bold', 'feint'},
	'23': {'italic'},
	'24': {'underline', 'double-underline'},
	'25': {'blink', 'rapid'},
	'27': {'inverse'},
	'28': {'invisible'},
	'29': {'cross'},
	'54': {'frame', 'encircle'},
	'55': {'overline'},
}

sets = {
	'1': 'bold',
	'2': 'feint',
	'3': 'italic',
	'4': 'underline',
	'5': 'blink',
	'6': 'rapid',
	'7': 'inverse',
	'8': 'invisible',
	'9': 'cross',

	'21': 'double-underline',
	'51': 'frame',
	'52': 'encircle',
	'53': 'overline',
}

rsts['0'] = {'text-color', 'cell-color', 'line-color'}
for x in sets.values():
	rsts['0'].update(x)

tty_16_color_names = [
	'black',
	'red',
	'green',
	'yellow',
	'blue',
	'magenta',
	'cyan',
	'white',
]

# Regular.
text_colors_16 = {
	str(30 + i): name
	for i, name in enumerate(tty_16_color_names)
}

# Brights.
text_colors_16.update({
	str(90 + i): name
	for i, name in enumerate(tty_16_color_names)
})

# Regular.
cell_colors_16 = {
	str(40 + i): name
	for i, name in enumerate(tty_16_color_names)
}

# Brights.
cell_colors_16.update({
	str(100 + i): name
	for i, name in enumerate(tty_16_color_names)
})

# Identify bright colors.
brights = set()
brights.update(map(str, range(100, 108)))
brights.update(map(str, range(90, 98)))

def xterm_color_palette(r, g, b):
	"""
	# Calculate the color value and color code from the relative &r, &g, &b index.

	# `starmap(xterm_color_palette, product(*map(range, (6,6,6))))` can be used to
	# build a full mapping of 24-bit color values and xterm codes.
	"""

	code = 16 + (r * 36) + (g * 6) + b
	red_value = green_value = blue_value = 0

	if r:
		red_value = r * 40 + 55
	if g:
		green_value = g * 40 + 55
	if b:
		blue_value = b * 40 + 55

	value = (red_value << 16) | (green_value << 8) | blue_value
	return (value, code)

def xterm_gray_palette(index):
	"""
	# Calculate the color value for the given gray &index.
	#
	# `map(xterm_gray_palette, range(24))` can be used to
	# build a full mapping of 24-bit color values and xterm codes.
	"""

	if index < 0:
		index = 0
	elif index > 23:
		index = 23

	base = index * 10 + 8
	return ((base << 16) | (base << 8) | base), index + 232

def xterm_index():
	"""
	# Construct and return a full index of color codes to their corresponding RGB value.
	"""

	idx = dict()
	idx.update(((v, k) for k, v in map(xterm_gray_palette, range(24))))
	idx.update(((v, k) for k, v in itertools.starmap(
		xterm_color_palette, itertools.product(range(6),range(6),range(6))
	)))
	return idx

# Translate xterm256 color palette codes to 24-bit RGB color values.
xterm_256_colors = xterm_index()

csi = "["
osc = "]"
st = "\\"

def csi_read_color(piter):
	"""
	# Read one to four values from &piter to form a 24-bit color value.

	# [ Exceptions ]
	# /ValueError/
		# When the first value read is not a recognized palette or
		# when any value is read that cannot be interpreted as an integer.
	"""

	try:
		ctype = next(piter) # Get identified color palette.
	except StopIteration:
		ctype = 0

	if ctype == '2':
		r = g = b = 0
		try:
			r = int(next(piter) or '0', 10)
			g = int(next(piter) or '0', 10)
			b = int(next(piter) or '0', 10)
		except StopIteration:
			pass
		return (r << 16 | g << 8 | b << 0)
	elif ctype == '5':
		try:
			return xterm_256_colors[int(next(piter) or '0', 10)]
		except StopIteration:
			return 0
	else:
		raise ValueError("unrecognized color palette: " + repr(ctype))

def brighten(color, delta):
	"""
	# Add &delta to each RGB field in &color.
	"""

	return (
		min(0xFF, ((color >> 16) + delta)) << 16
		| min(0xFF, (((color >> 8) & 0xFF) + delta)) << 8
		| min(0xFF, ((color & 0xFF) + delta))
	)

def integrate(index, snapshot, traits, *colors):
	"""
	# Reconstruct &snapshot with the changes in &traits and &colors.
	"""

	tc, cc, lc = colors

	if 'underline' in traits:
		underline = index['line-solid']
	else:
		underline = index['line-void']

	if 'feint' in traits:
		# Currently presumes feint is the only source of alpha.
		tc = (index['delta'] << 24) | (tc & 0xFFFFFF)
	else:
		tc &= 0xFFFFFF

	c = snapshot.update(
		textcolor = tc,
		cellcolor = cc,
		linecolor = lc,
		underline = underline,
		bold = ('bold' in traits),
		italic = ('italic' in traits),
	)

	return c, ('inverse' in traits)

def structure(index, snapshot, inverse):
	"""
	# Extract the color settings and traits from &snapshot.

	# Used by &transition to configure the mutable state that
	# will be modified by the SGR sequences.
	"""

	tc = snapshot.textcolor
	cc = snapshot.cellcolor
	lc = snapshot.linecolor

	state = set()
	if snapshot.bold:
		state.add('bold')
	if snapshot == snapshot.update(underline=index['line-solid']):
		state.add('underline')
	if snapshot.italic:
		state.add('italic')
	if (tc >> 24) > 0:
		state.add('feint')
	if inverse:
		state.add('inverse')

	return tc, cc, lc, state

def transition(colors, snapshot, inverse, deltas:str):
	"""
	# Interpret the SGR sequences in &deltas and apply them to the &snapshot.

	# [ Returns ]
	# Updated snapshot, inverse status, and effective snapshot.
	"""

	vg = colors['visible']
	tc, cc, lc, state = structure(colors, snapshot, inverse)
	if deltas:
		di = iter(deltas.split(';'))
	else:
		# Empty implies zero for SGR.
		di = iter(('0',))

	for code in di:
		if not code:
			code = '0'

		if code == '0':
			tc = vg.textcolor
			cc = vg.cellcolor
			lc = vg.linecolor
			state.clear()
		elif code in sets:
			# Set traits.
			state.add(sets[code])
		elif code in rsts:
			# Remove traits.
			state.difference_update(rsts[code])
			if 'feint' not in state:
				# Presuming feint is the only source of alpha.
				tc &= 0xFFFFFF
		elif code in text_colors_16:
			tc = colors[text_colors_16[code]]
			if code in brights:
				tc = brighten(tc, colors['delta'])
		elif code in cell_colors_16:
			cc = colors[cell_colors_16[code]]
			if code in brights:
				cc = brighten(cc, colors['delta'])
		elif code == '38':
			# Text color
			try:
				tc = csi_read_color(di)
			except ValueError:
				tc = vg.textcolor
		elif code == '48':
			# Cell color
			try:
				cc = csi_read_color(di)
			except ValueError:
				cc = vg.cellcolor
		elif code == '58':
			# Line color
			try:
				lc = csi_read_color(di)
			except ValueError:
				lc = vg.linecolor
		elif code == '39':
			tc = vg.textcolor
		elif code == '49':
			cc = vg.cellcolor
		elif code == '59':
			lc = vg.linecolor

	snapshot, inverse = integrate(colors, snapshot, frozenset(state), tc, cc, lc)
	esnapshot = snapshot

	if inverse:
		esnapshot = snapshot.update(
			textcolor = snapshot.cellcolor,
			cellcolor = snapshot.textcolor,
		)

	return snapshot, inverse, esnapshot

def annotate_backspaces(string):
	"""
	# Find the backspace sequences in &string and identify their traits.
	"""

	i = 0
	while (i := string.find('\x08', i)) >= 0:
		s = slice(i-1, i+2)
		seq = string[s]

		if len(seq) < 3:
			i = s.stop
			continue

		if seq[0] == seq[-1]:
			# Prioritize bold as the underline may not be
			# easily seen against the underscore.
			yield (s, seq[-1], 'bold')
		elif seq[0] == '_':
			yield (s, seq[-1], 'underline')
		elif seq[0] == '/':
			yield (s, seq[-1], 'italic')
		else:
			# No change to report.
			yield (s, seq[-1], None)
		i = s.stop

def trait(index, snapshot, trait):
	"""
	# Apply a single trait to the glyph template.
	"""

	if trait == 'underline':
		return snapshot.update(underline=index['line-solid'])
	elif trait == 'bold':
		return snapshot.update(bold=True)
	elif trait == 'italic':
		return snapshot.update(italic=True)
	else:
		# No adjustments to snapshot.
		pass

	return snapshot

def integrate_backspace_traits(index, snapshot, string):
	"""
	# Apply the identified changes in &deltas to string.
	"""

	edge = 0
	di = iter(annotate_backspaces(string))

	for s, rc, gtrait in di:
		if s.start > edge:
			yield (snapshot.inscribe(-2), string[edge:s.start])

		# Keep downstream redirects independent to force character unit isolation.
		yield (trait(index, snapshot, gtrait).inscribe(ord(rc)), string[s])
		edge = s.stop

	# Final area.
	if edge < len(string):
		yield (snapshot.inscribe(-2), string[edge:])

def identify_exclusions(string):
	"""
	# Isolate OSC-ST regions for hiding text regions.
	"""

	inclusion, *exclusions = string.split(osc)
	if inclusion:
		yield (False, inclusion)

	for escaped in exclusions:
		end = escaped.find(st)
		if end == -1:
			# No terminator.
			if escaped:
				yield (True, (osc, escaped, ''))
		else:
			# Exclude everything up to the terminator.
			yield (True, (osc, escaped[:end], st))
			# Include everything after.
			after = escaped[end+len(st):]
			if after:
				yield (False, after)

def context(theme):
	"""
	# Build an index from &theme for usage with &format.
	"""

	from ..cells.types import Line
	g = theme['default']

	return {
		# Glyph templates.
		'control': g.update(codepoint=-1),
		'obscured': g.update(codepoint=-3),
		'visible': g.update(codepoint=-2, linecolor=0x444444),

		# Line types.
		'line-double': Line.double,
		'line-solid': Line.solid,
		'line-void': Line.void,

		# tty-16 colors.
		'red': theme['red'].textcolor,
		'green': theme['green'].textcolor,
		'blue': theme['blue'].textcolor,
		'yellow': theme['yellow'].textcolor,
		'orange': theme['orange'].textcolor,
		'purple': theme['purple'].textcolor,
		'magenta': theme['magenta'].textcolor,
		'cyan': theme['cyan'].textcolor,
		'gray': theme['gray'].textcolor,
		'black': theme['black'].textcolor,
		'white': theme['white'].textcolor,

		# Quantity used to apply feint and bright.
		'delta': 0x33,
	}

def format(colors, line):
	"""
	# Interpret the SGR CSI codes in &line and emit pairs of glyphs and text.
	"""

	# Two snapshots are kept to manage &inverse as Glyph instances do not
	# have an "inverse" trait. &inverse represents this missing field, and
	# &esnapshot is the effective snapshot incoporating its effect when present.
	inverse = False
	esnapshot = snapshot = colors['visible']
	ctransition = functools.lru_cache(16)(functools.partial(transition, colors))

	# Handle OSC sequences.
	areas = identify_exclusions(line.ln_content)
	for area in areas:
		exclude, line_fragment = area
		if exclude:
			# line_fragment is OSC content event.
			if line_fragment[1].startswith('8;1;2-x') and line_fragment[1][-1] == '\x03':
				# Isolate status frame extension data.
				yield (colors['control'], line_fragment[0] + '8;1;2-x')
				yield (colors['control'], line_fragment[1][len('8;1;2-x'):-1])
				yield (colors['control'], '\x03' + line_fragment[-1])
			else:
				yield (colors['control'], ''.join(line_fragment))
			continue

		# Prepare CSI escapes.
		segments = line_fragment.split(csi)
		if not segments:
			continue

		# Resolve backspaces with optional trait, however cursed it may be.
		yield from integrate_backspace_traits(colors, esnapshot, segments[0])

		# Process CSIs
		for escape in segments[1:]:
			text = escape.lstrip('0123456789;:<=>?!"#$%&\'()*+,-./')
			terminator = text[0:1]
			seqstr = escape[:len(escape) - len(text)]

			if terminator == 'm':
				snapshot, inverse, esnapshot = ctransition(snapshot, inverse, seqstr)
			else:
				# Sequence, but not SGR.
				pass

			# Emit control field for the sequence so insertions can be properly addressed.
			yield (colors['control'], csi+seqstr+terminator)

			# Emit text following the sequence.
			yield from integrate_backspace_traits(colors, esnapshot, text[1:])
