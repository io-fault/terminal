"""
# Support functions for refraction query commands.
"""
from . import format
from . import types
from . import projection
from . import delta

def type():
	# Currently, just &format.Lambda.
	return format.prepare(format.files.root)

def refract(session, view, qtype, state, action):
	"""
	# Construct a Refraction for representing a query.
	"""

	meta = types.Reference(
		'/../',
		'query-instructions',
		format.files.root@'/dev',
		format.files.root@'/dev/void',
		None,
	)

	lrf = types.Refraction(
		meta,
		*session.open_type(format.files.root),
		list(map(str, [qtype, state])),
		delta.Log(),
	)
	lrf.configure(view.display.dimensions)
	lrf.activate = action # location.open or location.save
	view.version = lrf.log.snapshot()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 1, 2))
	last = lrf.elements[-1]
	lrf.focus[1].restore((0, 0, len(state)))
	session.defer(projection.refresh(lrf, view, 0))

	if not state:
		session.keyboard.set('insert')
	return lrf

def find(session, rf, event):
	"""
	# Perform a find operation against the subject's elements.
	"""

	*context, string = rf.elements
	session.cancel()
	subject = session.focus
	v, h = subject.focus
	subject.query['search'] = string
	ctl = subject.forward(len(subject.elements), v.get(), h.maximum)
	session.focus.find(ctl, string)
	session.deltas.append((session.focus, session.view))

def seek(session, rf, event):
	"""
	# Perform a seek operation on the refraction.
	"""

	try:
		*context, string = [y for y in (x.strip() for x in rf.elements) if y]
	except ValueError:
		# Empty
		session.cancel()
		return

	session.cancel()
	subject = session.focus

	if context:
		op, whence = ' '.join(context).split()
	else:
		try:
			op, whence = string.split()
		except ValueError:
			op = string
			whence = 'absolute'

		string = ''

	assert op == 'seek'

	if whence == 'absolute':
		string = string
		if string.startswith('-'):
			ln = len(subject.elements)
		else:
			ln = -1
	elif whence == 'relative':
		ln = subject.focus[0].get()
	else:
		log("Unrecognized seek whence " + repr(whence) + ".")
		return

	ln += int(string) if string else len(subject.elements)

	subject.seek(max(0, ln), 0)
	session.deltas.append((session.focus, session.view))

def getfield(fields, index):
	fa, fp = fields
	return (fa[index], *fp[index])

def prepare(rf, context, command):
	"""
	# Identify the requested change.
	"""

	rws, strctx, *index = context.strip().split()
	if index:
		# field indexes
		index = int(index[0])
		assert strctx == 'field'
		selector = (lambda lo: getfield(rf.fields(lo), index))
	else:
		assert strctx == 'line'
		selector = (lambda lo: (slice(0, None), 'line', rf.elements[lo]))

	di, arg = command.split(None, 1)
	op = {
		'prefix': (lambda a, t, f: (a.start, arg, "")),
		'suffix': (lambda a, t, f: (a.stop, arg, "")),
	}[di]

	return selector, op

def rewrite(session, rf, event):
	"""
	# Rewrite the lines or fields of a vertical range.
	"""

	context, command = rf.elements
	session.cancel()
	subject = session.focus

	s, d = prepare(subject, context, command)
	v, h = subject.focus
	lspan = v.slice()

	# Identify first IL.
	elements = subject.elements
	lil = format.Whitespace.il
	il = lil(elements[lspan.start])

	subject.log.checkpoint()
	for lo in range(lspan.start, lspan.stop):
		if il != lil(elements[lo]):
			# Match starting IL.
			continue
		try:
			selection = s(lo)
		except IndexError:
			# Handle shorter line cases by skipping them.
			continue
		else:
			position, sub, removed = d(*selection)
			subject.log.write(delta.Update(lo, sub, removed, position))
	subject.log.apply(subject.elements).commit().checkpoint()

	session.deltas.append((session.focus, session.view))
