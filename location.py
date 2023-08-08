"""
# Syntax type methods for structuring and rendering location fields.
"""
import functools
from fault.system.files import root
from fault.terminal.format.url import f_string as furl
from fault.terminal.format.path \
	import \
		route_colors as colors, \
		f_route_absolute as fapath, \
		f_route_path as frpath, \
		f_route_identifier as fipath
from . import types
from . import delta

def determine(context, path):
	"""
	# Identify the strings to use to represent the context path
	# and the subject path.

	# &path is usually identified relative to context, but in cases
	# where there is no common ancestor show as absolute.
	"""

	rseg = path.segment(context)
	if rseg:
		ipath = '/'.join(rseg)
	else:
		ipath = str(path)

	return str(context), ipath

def structure_path(rpath, line):
	# Most of this is compensation for the differences between
	# representing a &..system.files.Path and representing a path
	# that is consistent with the exact string.

	if rpath == root or line.startswith('/'):
		p = fapath(root@line)
	else:
		lpath = rpath@line
		if '/' not in line:
			# Just an identifier.
			return fipath(lpath)
		else:
			p = (frpath(rpath, lpath ** 1) + fipath(lpath))[1:]

	if line.endswith('/'):
		trailing = len(line) - len(line.rstrip('/'))
		for i in range(trailing):
			p.append(('path-separator', '/'))

	return p

def formatter(rpath, context):
	rp = context.terminal_type.normal_render_parameters
	def fmt_path(spath, *, Phrase=context.Phrase, Words=context.Words, Style=rp):
		return Phrase([
			Words((len(txt), txt, Style.apply(textcolor=colors[typ])))
			for typ, txt in spath
		])
	return fmt_path

def render(rpath, context, line):
	return formatter(rpath, context)(structure_path(rpath, line))

def type(lcontext, gcontext):
	"""
	# Construct the necessary processing functions for supporting
	# line structure, formatting, and rendering in a &.types.Refraction.
	"""
	lc = lcontext.delimit()
	structure = functools.partial(structure_path, lc)
	fmt = formatter(lc, gcontext)
	def render(line, *, structure=structure, format=fmt):
		return format(structure(line))
	return (lc, structure, fmt, render)

def compose(pathlines, *, default='/dev/null'):
	"""
	# Construct a Path from an iterable of path segments where all
	# leading segments up to the last are composed as the context
	# of the returned path.

	# Whitespace *only* lines are treated as empty strings,
	# but whitespace is verbatim in all other cases.

	# If the iterable has no path strings after filtering,
	# the &default is used.
	"""

	pathv = [x for x in pathlines if not x.isspace()]
	if not pathv:
		pathv = [default]

	*pathctxv, pathstr = pathv
	if pathstr.startswith('/'):
		# Ignore context if absolute.
		path = root@pathstr
	else:
		pathctx = (root@'/'.join(x.strip('/') for x in pathctxv)).delimit()
		path = pathctx@pathstr

	return path

def open(session, rf, event):
	"""
	# Respond to an activation event while focused on a location refraction.

	# Interprets the refractions' elements as a &Reference and constructs
	# a new refraction to represent the loaded resource.
	"""

	# Construct reference and load dependencies.
	dpath = (session.vertical, session.division)
	new = session.refract(compose(rf.elements))

	session.attach(dpath, new)
	session.keyboard.set('control')
	session.refocus()

	del rf.elements[:]
	rf.visible[0] = 0
	session.defer(session.chpath(dpath, new.origin, snapshot=rf.log.snapshot()))

def save(session, rf, event):
	"""
	# Respond to an activation event while focused on a location refraction
	# configured to save the elements to the identified location.

	# Interprets the refractions' elements as a path and performs the write operation
	# to that path.
	"""

	# Construct reference and load dependencies.
	dpath = (session.vertical, session.division)
	path = compose(rf.elements)

	session.refocus()
	target = session.focus
	session.save_resource(path, target.elements)
	session.keyboard.set('control')

	# Location heading.
	del rf.elements[:]
	rf.visible[0] = 0
	session.defer(session.chpath(dpath, target.origin, snapshot=rf.log.snapshot()))

def refract(view, pathcontext, path, action):
	"""
	# Construct a Refraction for representing a location path.
	"""

	# Create the refraction on demand as there is little need
	# for maintaining cursor and visibility state across use.
	# Only relevant state is the per-view resource history.

	# Unused, but make available for invariant.
	# Repeat Session.relocate operations will result in reconstructing
	# the location refraction.
	meta = types.Reference(
		'/../resource-indicator',
		'resource-location',
		root@'/dev',
		root@'/dev/void',
		None,
	)

	lrf = types.Refraction(
		meta,
		*type(pathcontext, view.display),
		list(map(str, determine(pathcontext, path))),
		delta.Log(),
	)
	lrf.configure(view.display.dimensions)
	lrf.activate = action # location.open or location.save
	view.version = lrf.log.snapshot()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 1, 2))
	last = lrf.elements[-1]
	name = last.rfind('/') + 1
	lrf.focus[1].restore((name, name, sum(map(len, lrf.elements))))

	return lrf
