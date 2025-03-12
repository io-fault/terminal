"""
# Session retention and restoration functions.
"""
from fault.system import files

# lfht format parsing and serialization.
from fault.status.transport import sequence, structure

def structure_selection(path:str, fs=files.root, null=files.root@'/dev/null'):
	"""
	# Parse the selection reference.
	"""

	positions = None

	rpath, vpositions = path.rsplit('/', 1)
	if rpath in {'None', '-', 'dev/null'} or (rpath, vpositions) == ('/dev', 'null'):
		return null, positions

	try:
		if vpositions and not vpositions.isspace():
			positions = list(int(x) for x in vpositions.split() if x)
	except ValueError:
		positions = None

	return fs@rpath, positions

def selection_test(s):
	if s[:1] in {'#', '\t'}:
		return False

	if s.find('/') != -1:
		return True

	return False

def sequence_selection(vrecord, Separator='/', Root='/'):
	"""
	# Serialize the selection reference; resource path, view position, and cursor position.
	"""

	fp, a = vrecord
	if fp is None:
		return '-'
	apath = Root
	av = list(a)

	# Normalize the partitions. (Eliminate redundant slashes)
	for p in fp.partitions():
		filtered = list(filter(None, p))
		if filtered:
			if apath == Root:
				# First partition.
				apath += Separator.join(filtered) + Separator
			else:
				# Second.
				apath += Separator + Separator.join(filtered)

	if sum(av) > 0:
		addressing = '/' + ' '.join(map(str, av))
	else:
		addressing = '/'

	return apath.rstrip(Separator) + addressing

def structure_frames(frames):
	"""
	# Structure the lfht image into a form that can be read by
	# by &.elements.Session.restore.
	"""

	for frame_id, lines in frames:
		layout = []
		fstatus = lines[0]
		vi, di, flstr = fstatus.strip().split(' ', maxsplit=2)

		for i, s in enumerate(flstr.split()):
			if '*' in s:
				x, width = map(int, s.split('*'))
			else:
				x = int(s)
				width = 1

			layout.append((x, width))

		divcount = sum(x[0] for x in layout)
		files = [structure_selection(x) for x in lines[1:] if selection_test(x)]
		resources = files[0:divcount]
		returns = files[divcount:None]

		vi = int(vi)
		di = int(di)
		yield (frame_id.strip() or None, vi, di, divcount, layout, resources, returns)

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

def sequence_frames(session):
	"""
	# Construct the lfht image representing the frames.
	"""

	yield from (
		(frame_id or '', [
				' '.join(map(str, (vi, di))) + \
				' ' + \
				''.join(frame_layout_string(layout))
			] + list(sequence_selection(r) for r in resources + returns)
		)
		for (frame_id, vi, di, layout, resources, returns) in session
	)
