"""
# Support functions for refraction query commands.
"""
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
	lf = meta.forms
	meta.extend_lines(map(lf.ln_interpret, [qtype + ' ' + state]))
	meta.commit()
	lrf = Refraction(meta)
	lrf.configure(view.area)
	lrf.activate = action # location.open or location.save
	view.version = lrf.source.version()

	# Set the range to all lines and place the cursor on the relative path..
	lrf.focus[0].restore((0, 0, 1))
	last = lrf.source.elements[-1]
	lrf.focus[1].restore((0, len(qtype) + 1, len(qtype) + len(state) + 1))
	session.dispatch_delta(lrf.refresh(view, 0))

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
	src = rf.source

	# Horizontal Range
	lo, co, lines = rf.take_horizontal_range()
	rf.focus[1].magnitude = 0
	readlines = joinlines(Decode('utf-8').decode)
	readlines.send(None)
	readlines = readlines.send
	src.commit()

	cmd = '\n'.join(lines).split()
	for exepath in executables(cmd[0]):
		inv = Invocation(str(exepath), tuple(cmd))
		break
	else:
		# No command found.
		return

	c = Completion(rf, -1)
	i = Insertion(rf, (lo, co, ''), readlines)
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
	src = rf.source

	cmd = system.split()
	for exepath in query.executables(cmd[0]):
		inv = Invocation(str(exepath), tuple(cmd))
		break
	else:
		# No command found.
		return

	c = Completion(rf, -1)
	lo = rf.focus[0].get()
	co = rf.focus[1].get()
	readlines = Decode('utf-8').decode

	if lo >= src.ln_count():
		src.ln_initialize()
		src.commit()
	target_line = src.sole(lo)

	i = Insertion(rf, (lo, co, ''), readlines)
	i.level = target_line.ln_level
	if i.level:
		# Maintain initial indentation context on first line,
		# and make sure that there is a line to write into.
		src.insert_lines(lo, [src.forms.ln_interpret("", level=i.level)])
		src.commit()

	pid = session.io.invoke(c, i, None, inv)
	ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
	rf.annotate(ca)

def bufferlines(limit, lines):
	buffer = b''
	for l in lines:
		buffer += l
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

	readlines = Decode('utf-8').decode
	src = rf.source
	src.checkpoint()

	c = Completion(rf, -1)
	start, co, lines = rf.take_vertical_range()
	src.commit()

	rf.focus[0].magnitude = 0
	rf.delta(start, start + len(lines))

	i = Insertion(rf, (start, 0, ''), readlines)
	lfb = src.forms.lf_codec.sequence
	lfl = src.forms.lf_lines.sequence
	try:
		cil = min(li.ln_level for li in lines if li.ln_content)
	except ValueError:
		cil = 0
	i.level = cil

	# Maintain initial indentation context on first line,
	# and make sure that there is a line to write into.
	src.insert_lines(start, [src.forms.ln_interpret("", level=cil)])
	src.commit()

	ilines = ((li.ln_level - cil, li.ln_content) for li in lines)

	x = Transmission(rf, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

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
	lines = rf.source.serialize(*rf.focus[0].range())
	x = Transmission(rf, bufferlines(2048, lines), b'', 0)

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
	src = rf.source
	command, string = ' '.join(x.ln_content for x in src.select(0, src.ln_count())).split(' ', 1)
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
