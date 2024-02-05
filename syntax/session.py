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
		layout = tuple(map(int, lines[0].split()))
		count = sum(layout)
		files = [fileref(x) for x in lines[1:] if filetest(x)]
		resources = files[0:count]
		returns = files[count:None]
		yield (frame_id.strip() or None, layout, resources, returns)

def sequence_frames(session, *, Render=transport.sequence):
	return Render(
		(frame_id or '', [
				' '.join(map(str, layout))
			] + list(filepath(r) for r in resources + returns)
		)
		for (frame_id, layout, resources, returns) in session
	)
