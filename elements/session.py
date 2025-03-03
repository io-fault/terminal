"""
# Session retention and restoration functions.
"""
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

def filepath(fp, Separator='/', Root='/'):
	if fp is None:
		return '-'
	apath = Root

	for p in fp.partitions():
		filtered = list(filter(None, p))
		if filtered:
			if apath == Root:
				# First partition.
				apath += Separator.join(filtered) + Separator
			else:
				# Second.
				apath += Separator + Separator.join(filtered)

	return apath.rstrip(Separator)

def structure_frames(session:str, *, Interpret=transport.structure):
	"""
	# Structure the lfht image into a form that can be read by
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

def frame_layout_string(layout):
	"""
	# Yield the string that represents the given &layout.
	"""

	prefix = ''
	for vertical in layout:
		yield prefix
		divcount, width = vertical

		if width is not None and width != 1:
			yield str(divcount) + '*' + str(width)
		else:
			yield str(divcount)
		prefix = ' '

def sequence_frames(session, *, Render=transport.sequence):
	"""
	# Construct the lfht image representing the frames.
	"""

	return Render(
		(frame_id or '', [
				''.join(frame_layout_string(layout))
			] + list(filepath(r) for r in resources + returns)
		)
		for (frame_id, layout, resources, returns) in session
	)
