"""
# Syntax type methods for structuring and rendering location fields.
"""
import os.path
import functools
from fault.system import files

from . import types
from . import delta
from . import format

def format_path(root, extension, *, separator='/', _is_link=os.path.islink):
	"""
	# Format the path components in &extension relative to &root.
	"""

	current = root
	for f in extension[:-1]:
		if not f:
			yield ('path-empty', '')
		else:
			current = current/f

			if f in {'.', '..'}:
				yield ('relatives', f)
			else:
				if _is_link(current):
					yield ('path-link', f)
				else:
					try:
						typ = current.fs_type()
					except OSError:
						typ = 'warning'

					if typ == 'directory':
						yield ('path-directory', f)
					elif typ == 'void':
						yield ('file-not-found', f)
					else:
						yield (typ, f)

		yield ('path-separator', separator)

	f = extension[-1]
	final = current/f
	try:
		typ = final.fs_type()
	except OSError:
		typ = 'warning'

	# Slightly different from path segments.
	if typ == 'data':
		try:
			if final.fs_executable():
				typ = 'executable'
			elif f[:1] == '.':
				typ = 'dot-file'
			else:
				# No subtype override.
				pass
		except OSError:
			typ = 'warning'
	elif typ == 'void':
		typ = 'file-not-found'
	else:
		# No adjustments necessary.
		pass

	yield (typ, f)

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

def structure_path(rpath, line, *, separator='/'):
	"""
	# Structure the path components of &line relative to &rpath.
	# If &line begins with a root directory, it is interpreted absolutely.
	"""

	s = separator
	if line:
		if line.startswith(s):
			i = (format_path(files.root, line.split(s), separator=s))
		else:
			i = (format_path(rpath, line.split(s), separator=s))
	else:
		i = ()

	l = [('indentation', '')]
	l.extend(i)
	l.append(('trailing-whitespace', ''))
	return l

def render(theme, rpath, context, line):
	return format.compose(context, theme, structure_path(rpath, line))

def type(theme, lcontext, gcontext):
	"""
	# Construct the necessary processing functions for supporting
	# line structure, formatting, and rendering in a &.types.Refraction.
	"""

	lc = lcontext.delimit()
	structure = functools.partial(structure_path, lc)
	fmt = functools.partial(format.compose, theme)
	def render(line, *, structure=structure, fmt=fmt):
		return fmt(structure(line))
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
		path = files.root@pathstr
	else:
		pathctx = (files.root@'/'.join(x.strip('/') for x in pathctxv)).delimit()
		if pathstr:
			path = pathctx@pathstr
		else:
			path = pathctx

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
	session.device.update(session.chpath(dpath, new.origin, snapshot=rf.log.snapshot()))

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
	session.device.update(session.chpath(dpath, target.origin, snapshot=rf.log.snapshot()))

def refract(theme, view, pathcontext, path, action):
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
		files.root@'/dev',
		files.root@'/dev/void',
		None,
	)

	lrf = types.Refraction(
		meta,
		*type(theme, pathcontext, view.area),
		list(map(str, determine(pathcontext, path))),
		delta.Log(),
	)
	lrf.configure(view.area)
	lrf.activate = action # location.open or location.save
	view.version = lrf.log.snapshot()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 1, 2))
	last = lrf.elements[-1]
	name = last.rfind('/') + 1
	lrf.focus[1].restore((name, name, len(last)))

	return lrf
