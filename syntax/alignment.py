"""
# Functions controlling alignment and limits.

# [ Parameters ]
# /total/
	# The available units prior to a change being applied.
# /visible/
	# The units that can be visible (height or width).
# /position/
	# The current position of the view within &total.
# /offset/
	# The point at which a change is occurring relative to &total.
# /quantity/
	# The size of the requested change.
"""

def delta(*args):
	"""
	# Calculate the view's position after an insertion or deletion.
	"""

	if args[-1] == 0:
		# Zero change.
		return args[2] # position
	elif args[-1] > 0:
		return insert(*args)
	else:
		return delete(*args)

def insert(total, visible, position, offset, quantity, *, max=max):
	"""
	# Calculate the change in the view's &position necessary to
	# maintain the current image after the insertion is performed.
	"""

	if position == 0 and total < visible:
		# No adjustements when on first page.
		if total > visible:
			# Transition to last page.
			return max(0, total - visible)
		else:
			return position

	if position + visible >= (total - quantity):
		# Last page insertion, force alignment.
		return max(0, total - visible)
	elif offset < position:
		return position + quantity
	else:
		# No position change.
		assert offset >= position

	return position

def delete(total, visible, position, offset, quantity, *, max=max, min=min):
	"""
	# Calculate the change in the view's &position necessary to
	# maintain the image after the deletion is performed.
	"""
	assert quantity <= (total - quantity)

	if position == 0:
		# No adjustements when on first page.
		return position

	d_end = offset + quantity
	max_p = max(0, total - visible)

	if d_end < position:
		position -= quantity
	else:
		if position + visible >= (total - quantity):
			# Last page deletion, force alignment.
			return max_p

		if offset >= position:
			# Deletion occurred after position.
			# No change in position unless &total changes
			# force it.
			pass
		else:
			# Overlap.
			assert d_end - position > 0
			position = offset

	return min(position, max_p)

def scroll(*args):
	"""
	# Constrain a relative scroll request.
	"""

	if args[-1] == 0:
		# Zero change.
		return (args[-2], 0, (0, 0))
	elif args[-1] > 0:
		return forward(*args)
	else:
		return backward(*args[:3], -args[-1])

def forward(total, visible, position, quantity, *, min=min, max=max):
	"""
	# Constrain view changes so that they never cross boundaries, zero and &total.

	# [ Returns ]
	# # The new absolute &position.
	# # The new, constrained, &quantity.
	# # The relative area left vacant as a tuple pair.
	"""

	# Limit the scroll to the absolute end minus the visible.
	# The maximums of zero handle the exception case where a
	# forwards scroll is performed with `total < visible`.
	start = max(0, min(position + quantity, total - visible))
	change = max(0, start - position)

	# The critical point here is to make sure that the
	# minimum of the visible or change is removed from the edge.
	edge = min(total, start + visible)

	return (start, change, (edge - min(change, visible), edge))

def backward(total, visible, position, quantity, *, min=min, max=max):
	"""
	# Constrain view changes so that they never cross boundaries, zero and &total.

	# [ Returns ]
	# # The new absolute &position.
	# # The new, constrained, &quantity.
	# # The relative area left vacant as a tuple pair.
	"""

	# Backwards, moving lines down.
	start = max(0, position - quantity)
	change = start - position

	return (start, change, (start, min(start - change, start + visible)))

def scroll_backward(area, quantity):
	"""
	# Move all lines backward by &quantity copying over the initial &quantity lines.

	# (illustration)`[||||||||] -> [xxx|||||<<]`
	"""

	return (
		area.__class__(
			area.top_offset + 0,
			area.left_offset + 0,
			area.lines - quantity,
			area.span
		),
		area.__class__(
			area.top_offset + quantity,
			area.left_offset + 0,
			0, 0
		),
	)

def scroll_forward(area, quantity):
	"""
	# Move all lines forward by &quantity copying over the final &quantity lines.

	# (illustration)`[||||||||] -> [>>|||||xxx]`
	"""

	return (
		area.__class__(
			area.top_offset + quantity,
			area.left_offset + 0,
			area.lines - quantity,
			area.span
		),
		area.__class__(
			area.top_offset + 0,
			area.left_offset + 0,
			0, 0
		),
	)

def start_relative_delete(area, start, stop):
	"""
	# Move the lines below &stop up to &start.

	# (illustration)`[||||start | stop||||] -> [||||xxx||||<<]`
	"""

	return (
		area.__class__(
			area.top_offset + start,
			area.left_offset + 0,
			area.lines - stop,
			area.span
		),
		area.__class__(
			area.top_offset + stop,
			area.left_offset + 0,
			0, 0
		),
	)

def start_relative_insert(area, start, stop):
	"""
	# Move the lines above &start down next to &stop.

	# (illustration)`[||||-||||] -> [||||start stop>>|xxx]`
	"""

	d = stop - start
	return (
		area.__class__(
			area.top_offset + stop,
			area.left_offset + 0,
			(area.lines - start) - d,
			area.span
		),
		area.__class__(
			area.top_offset + start,
			area.left_offset + 0,
			0, 0
		),
	)

def stop_relative_insert(area, start, stop):
	"""
	# Copy the lines above &stop up directly above &start overwriting initial lines.

	# (illustration)`[||||-||||] -> [xxx|<<start stop||||]`
	"""

	d = stop - start
	return (
		area.__class__(
			area.top_offset + 0,
			area.left_offset + 0,
			start - d,
			area.span
		),
		area.__class__(
			area.top_offset + d,
			area.left_offset + 0,
			0, 0
		),
	)

def stop_relative_delete(area, start, stop):
	"""
	# Copy the lines above &start down next to &stop.

	# (illustration)`[||||start | stop||||] -> [>>||||xxx||||]`
	"""

	return (
		area.__class__(
			area.top_offset + (stop - start),
			area.left_offset + 0,
			start,
			area.span
		),
		area.__class__(
			area.top_offset + 0,
			area.left_offset + 0,
			0, 0
		),
	)
