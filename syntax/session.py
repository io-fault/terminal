"""
# Session retention and restoration functions.
"""
from fault.context.tools import interlace
from fault.status import transport
from fault.system import process, files

def fileref(path:str, fs=files.root, null=files.root@'/dev/null'):
	if path in {'None', '-', '/dev/null'}:
		return null
	return fs@path

def filetest(s):
	first = s[:1]

	if first == '/':
		return True
	elif first in {'#', '\t'}:
		return False

	return False

def filepath(fp):
	if fp is None:
		return '-'
	return '/' + '//'.join(map('/'.join, fp.partitions()))

def structure_frames(session:str, *, Interpret=transport.structure):
	"""
	# Structure the sequenced session text into a form accepted
	# by &.elements.Session.restore.
	"""

	for frame_id, lines in Interpret(session):
		layout = []
		for i, s in enumerate(lines[0].split()):
			if '*' in s:
				x, width = map(int, s.split('*'))
			else:
				x = int(s)
				width = 1

			layout.append((x, width))

		divcount = sum(x[0] for x in layout)
		files = [fileref(x) for x in lines[1:] if filetest(x)]
		resources = files[0:divcount]
		returns = files[divcount:None]

		yield (frame_id.strip() or None, divcount, layout, resources, returns)

def sequence_frames(session, *, Render=transport.sequence):
	return Render(
		(frame_id or '', [
				' '.join(map(str, layout))
			] + list(filepath(r) for r in resources + returns)
		)
		for (frame_id, layout, resources, returns) in session
	)
