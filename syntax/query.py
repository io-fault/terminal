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

def refract(session, frame, view, qtype, state, action):
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

	from .elements import Refraction
	lrf = Refraction(
		meta,
		*session.open_type(format.files.root),
		list(map(str, [qtype + ' ' + state])),
		delta.Log(),
	)
	lrf.configure(view.area)
	lrf.activate = action # location.open or location.save
	view.version = lrf.log.snapshot()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 0, 1))
	last = lrf.elements[-1]
	lrf.focus[1].restore((0, len(qtype) + 1, len(qtype) + len(state) + 1))
	session.dispatch_delta(projection.refresh(lrf, view, 0))

	if not state:
		session.keyboard.set('insert')
	return lrf

def execute(session, frame, rf, system):
	"""
	# Send the selected elements to the device manager.
	"""

	from .system import Completion, Insertion, Invocation, Decode
	from .annotations import ExecutionStatus
	from fault.system import query

	cmd = system.split()
	for exepath in query.executables(cmd[0]):
		inv = Invocation(str(exepath), tuple(cmd))
		break
	else:
		# No command found.
		return

	c = Completion(rf, -1)
	ln = rf.focus[0].get()
	co = rf.focus[1].get()
	readlines = Decode('utf-8').decode
	i = Insertion(rf, (ln, co), readlines)
	pid = session.io.invoke(c, i, None, inv)
	ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
	rf.annotate(ca)

def issue(session, frame, rf, event):
	"""
	# Select and execute the target action.
	"""

	target, view = frame.select((frame.vertical, frame.division))
	command, string = ' '.join(rf.elements).split(' ', 1)
	index[command](session, frame, target, string)
	session.deltas.append((target, view))

def find(session, frame, rf, string):
	"""
	# Perform a find operation against the subject's elements.
	"""

	session.dispatch_delta(frame.cancel())
	v, h = rf.focus
	rf.query['search'] = string
	ctl = rf.forward(len(rf.elements), v.get(), h.maximum)
	rf.find(ctl, string)

def seek(session, frame, rf, string):
	"""
	# Perform a seek operation on the refraction.
	"""

	session.dispatch_delta(frame.cancel())

	try:
		whence, target = string.split()
	except ValueError:
		# Empty
		return

	target = target.strip()

	if whence == 'absolute':
		if target.startswith('-'):
			ln = len(rf.elements)
		else:
			ln = -1
	elif whence == 'relative':
		ln = rf.focus[0].get()
	else:
		log("Unrecognized seek whence " + repr(whence) + ".")
		return

	ln += int(target) if target else len(rf.elements)

	rf.seek(max(0, ln), 0)

def getfield(fields, index):
	fa, fp = fields
	return (fa[index], *fp[index])

def prepare(rf, command):
	"""
	# Identify the requested change.
	"""

	strctx, remainder = command.split(None, 1)

	if strctx == 'field':
		*index, di, arg = remainder.strip().split()
		# field indexes
		index = int(index[0])
		assert strctx == 'field'
		selector = (lambda lo: getfield(rf.fields(lo), index))
	elif strctx == 'line':
		di, arg = remainder.strip().split()
		selector = (lambda lo: (slice(0, None), 'line', rf.elements[lo]))

	op = {
		'prefix': (lambda a, t, f: (a.start, arg, "")),
		'suffix': (lambda a, t, f: (a.stop, arg, "")),
	}[di]

	return selector, op

def rewrite(session, frame, rf, command):
	"""
	# Rewrite the lines or fields of a vertical range.
	"""

	session.dispatch_delta(frame.cancel())

	s, d = prepare(rf, command)
	v, h = rf.focus
	lspan = v.slice()

	# Identify first IL.
	elements = rf.elements
	lil = format.Whitespace.il
	il = lil(elements[lspan.start])

	rf.log.checkpoint()
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
			rf.log.write(delta.Update(lo, sub, removed, position))
	rf.log.apply(rf.elements).commit().checkpoint()

index = {
	'seek': seek,
	'search': find,
	'rewrite': rewrite,
	'system': execute,
}
