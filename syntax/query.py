"""
# Support functions for refraction query commands.
"""
from . import projection
from . import delta
from . import types

def refract(session, frame, view, qtype, state, action):
	"""
	# Construct a Refraction for representing a query.
	"""

	from .elements import Resource, Refraction
	from fault.system import files
	ref = types.Reference(
		session.host,
		'/../',
		'query-instructions',
		files.root@'/dev',
		files.root@'/dev/void',
	)

	meta = Resource(ref, session.load_type('lambda'))
	meta.elements[:] = list(map(str, [qtype + ' ' + state]))
	lrf = Refraction(meta)
	lrf.configure(view.area)
	lrf.activate = action # location.open or location.save
	view.version = lrf.source.version()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 0, 1))
	last = lrf.source.elements[-1]
	lrf.focus[1].restore((0, len(qtype) + 1, len(qtype) + len(state) + 1))
	session.dispatch_delta(projection.refresh(lrf, view, 0))

	if not state:
		session.keyboard.set('insert')
	return lrf

def joinlines(decoder, linesep='\n', character=''):
	# Used in conjunction with an incremental decoder to collapse line ends.
	data = (yield None)
	while True:
		buf = decoder(data)
		data = (yield buf.replace(linesep, character))

def substitute(session, frame, rf):
	"""
	# Send the selected elements to the device manager.
	"""

	from .system import Completion, Insertion, Invocation, Decode
	from .annotations import ExecutionStatus
	from fault.system.query import executables

	# Horizontal Range
	lo, co, lines = rf.take_horizontal_range()
	rf.focus[1].magnitude = 0
	readlines = joinlines(Decode('utf-8').decode)
	readlines.send(None)
	readlines = readlines.send
	rf.source.commit()

	cmd = '\n'.join(lines).split()
	for exepath in executables(cmd[0]):
		inv = Invocation(str(exepath), tuple(cmd))
		break
	else:
		# No command found.
		return

	c = Completion(rf, -1)
	i = Insertion(rf, (lo, co), readlines)
	pid = session.io.invoke(c, i, None, inv)
	ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
	rf.annotate(ca)

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

def sendlines(encoder, limit, lines):
	buffer = b''
	for l in lines:
		buffer += encoder(l + '\n')
		if len(buffer) > limit:
			yield buffer
			buffer = b''

	if buffer:
		yield buffer

def transform(session, frame, rf, system):
	"""
	# Send the selected elements to the device manager.
	"""

	from .system import Completion, Insertion, Transmission, Invocation, Decode, Encode
	from .annotations import ExecutionStatus
	from fault.system import query

	cmd = system.split()
	for exepath in query.executables(cmd[0]):
		inv = Invocation(str(exepath), tuple(cmd))
		break
	else:
		# No command found.
		return

	src = rf.source
	src.checkpoint()

	c = Completion(rf, -1)
	start, co, lines = rf.take_vertical_range()
	src.commit()
	rf.focus[0].magnitude = 0
	rf.delta(start, start + len(lines))

	readlines = Decode('utf-8').decode
	i = Insertion(rf, (start, co), readlines)
	x = Transmission(rf, sendlines(Encode().encode, 2048, lines), b'', 0)

	# Trigger first buffer.
	x.transferred(b'')

	pid = session.io.invoke(c, i, x, inv)

	# Report status via annotation.
	ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
	rf.annotate(ca)

def transmit(session, frame, rf, system):
	"""
	# Send the selected elements to the system command.
	"""

	from .system import Completion, Transmission, Invocation, Encode
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
	lines = rf.source.elements[rf.focus[0].slice()]
	x = Transmission(rf, sendlines(Encode().encode, 2048, lines), b'', 0)

	# Trigger first buffer.
	x.transferred(b'')

	pid = session.io.invoke(c, None, x, inv)

	# Report status via annotation.
	ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
	rf.annotate(ca)

def issue(session, frame, rf, event):
	"""
	# Select and execute the target action.
	"""

	target, view = frame.select((frame.vertical, frame.division))
	command, string = ' '.join(rf.source.elements).split(' ', 1)
	index[command](session, frame, target, string)
	frame.deltas.append((target, view))

def find(session, frame, rf, string):
	"""
	# Perform a find operation against the subject's elements.
	"""

	v, h = rf.focus
	rf.query['search'] = string
	ctl = rf.forward(len(rf.source.elements), v.get(), h.maximum)
	rf.find(ctl, string)

def seek(session, frame, rf, string):
	"""
	# Perform a seek operation on the refraction.
	"""

	try:
		whence, target = string.split()
	except ValueError:
		# Empty
		return

	target = target.strip()

	if whence == 'absolute':
		if target.startswith('-'):
			ln = len(rf.source.elements)
		else:
			ln = -1
	elif whence == 'relative':
		ln = rf.focus[0].get()
	else:
		log("Unrecognized seek whence " + repr(whence) + ".")
		return

	ln += int(target) if target else len(rf.source.elements)

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
		selector = (lambda lo: (slice(0, None), 'line', rf.source.elements[lo]))

	op = {
		'prefix': (lambda a, t, f: (a.start, arg, "")),
		'suffix': (lambda a, t, f: (a.stop, arg, "")),
		'replace': (lambda a, t, f: (a.start, arg, f)),
	}[di]

	return selector, op

def rewrite(session, frame, rf, command):
	"""
	# Rewrite the lines or fields of a vertical range.
	"""

	s, d = prepare(rf, command)
	v, h = rf.focus
	lspan = v.slice()

	# Identify first IL.
	src = rf.source
	ln = src.sole(lspan.start)
	il = ln.ln_level

	# Force checkpoint.
	src.checkpoint()

	for lo in range(lspan.start, lspan.stop):
		if il != src.sole(lo).ln_level:
			# Match starting IL.
			continue

		try:
			selection = s(lo)
		except IndexError:
			# Handle shorter line cases by skipping them.
			continue
		else:
			co, sub, removed = d(*selection)
			deletion = src.substitute_codepoints(lo, co, co + len(removed), sub)
			assert deletion == removed

	src.checkpoint()

index = {
	'seek': seek,
	'search': find,
	'rewrite': rewrite,
	'system': execute,
	'system-map': transform,
	'transmit': transmit,
}
