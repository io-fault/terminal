"""
# Syntax type methods for structuring and rendering location fields.
"""
import os.path
import functools
from fault.system import files

from . import types

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

def open(session, frame, rf, event):
	"""
	# Respond to an activation event while focused on a location refraction.

	# Interprets the refractions' elements as a &Reference and constructs
	# a new refraction to represent the loaded resource.
	"""

	src = rf.source

	# Construct reference and load dependencies.
	dpath = (frame.vertical, frame.division)
	new = session.refract(compose(li.ln_content for li in src.select(0, 2)))

	session.dispatch_delta(frame.attach(dpath, new).refresh())
	session.keyboard.set('control')
	frame.refocus()

	del src.elements[:]
	rf.visible[0] = 0
	session.dispatch_delta(frame.chpath(dpath, new.source.origin, snapshot=src.version()))

def save(session, frame, rf, event):
	"""
	# Respond to an activation event while focused on a location refraction
	# configured to save the elements to the identified location.

	# Interprets the refractions' elements as a path and performs the write operation
	# to that path.
	"""

	src = rf.source

	# Construct reference and load dependencies.
	dpath = (frame.vertical, frame.division)
	path = compose(li.ln_content for li in src.select(0, 2))

	frame.refocus()
	target = frame.focus
	session.store_resource(target.source)
	session.keyboard.set('control')

	# Location heading.
	del src.elements[:]
	rf.visible[0] = 0
	session.dispatch_delta(frame.chpath(dpath, target.source.origin, snapshot=src.version()))

def refract(lf, view, pathcontext, path, action):
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
		None,
		'/../resource-indicator',
		'resource-location',
		files.root@'/dev',
		files.root@'/dev/void',
	)

	from dataclasses import replace
	from .elements import Refraction, Resource
	src = Resource(meta, lf)
	src.extend_lines(map(lf.ln_interpret, determine(pathcontext, path)))
	src.commit()

	rf = Refraction(src)
	pathfields = replace(lf.lf_fields, separation=(lambda: pathcontext@src.sole(0).ln_content))
	rf.forms = lf.replace(lf_fields=pathfields)
	rf.configure(view.area)
	rf.activate = action # location.open or location.save
	view.version = src.version()

	# Set the range to all lines and place the cursor on the relative path..
	rf.focus[0].restore((0, 1, 2))
	last = src.sole(1)
	name = last.ln_content.rfind('/') + 1
	rf.focus[1].restore((name, name, last.ln_length))

	return rf
