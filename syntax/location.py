"""
# Syntax type methods for structuring and rendering location fields.
"""
from fault.system import files

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
	ref = session.reference(compose(li.ln_content for li in src.select(0, 2)))
	src = session.import_resource(ref)
	new = rf.__class__(src)

	session.dispatch_delta(frame.attach(dpath, new))
	session.keyboard.set('control')
	frame.refocus()

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

def configure_path(src, pathcontext, path):
	src.delete_lines(0, src.ln_count())
	src.extend_lines(map(src.forms.ln_interpret, determine(pathcontext, path)))
	src.commit()

def configure_cursor(rf):
	# Set the range to all lines and place the cursor on the relative path..
	rf.focus[0].restore((0, 1, 2))
	last = rf.source.sole(1)
	name = last.ln_content.rfind('/') + 1
	rf.focus[1].restore((name, name, last.ln_length))
