"""
# Delta and snapshot rendering support for &types.View frame updates.
"""
from . import delta
from . import alignment
from . import types

def render(rf, view, *lines):
	"""
	# Update the &view representations of &lines from &rf.elements.

	# [ Returns ]
	# Iterable of &view.display produced instructions ready for transmission.
	"""

	start_of_view, left = rf.visible
	count = len(rf.elements)

	for lo in lines:
		rlo = lo - start_of_view
		if lo < count:
			line = rf.elements[lo]
		else:
			line = ""
		ph = rf.render(line)
		area = slice(rlo, rlo+1)
		view.update(area, (ph,))
		yield from view.render(area)

def scroll_backward(ctx, quantity):
	"""
	# Move all lines backward by &quantity copying over the initial &quantity lines.

	# (illustration)`[||||||||] -> [xxx|||||<<]`
	"""

	return ctx.replicate(
		(0, 0),
		(ctx.width, ctx.height - quantity),

		# Destination Point
		(0, quantity),
	)

def scroll_forward(ctx, quantity):
	"""
	# Move all lines forward by &quantity copying over the final &quantity lines.

	# (illustration)`[||||||||] -> [>>|||||xxx]`
	"""

	return ctx.replicate(
		(0, quantity),
		(ctx.width, ctx.height),

		# Destination Point
		(0, 0),
	)

def start_relative_delete(ctx, start, stop):
	"""
	# Move the lines below &stop up to &start.

	# (illustration)`[||||start | stop||||] -> [||||xxx||||<<]`
	"""

	return ctx.replicate(
		(0, stop),
		(ctx.width, ctx.height),

		# Destination Point
		(0, start),
	)

def start_relative_insert(ctx, start, stop):
	"""
	# Move the lines above &start down next to &stop with &matrix.Context.replicate.

	# (illustration)`[||||-||||] -> [||||start stop>>|xxx]`
	"""

	d = stop - start
	return ctx.replicate(
		(0, start),
		(ctx.width, ctx.height - d),

		# Destination Point
		(0, stop),
	)

def stop_relative_insert(ctx, start, stop):
	"""
	# Copy the lines above &stop up directly above &start overwriting initial lines.

	# (illustration)`[||||-||||] -> [xxx|<<start stop||||]`
	"""

	return ctx.replicate(
		(0, stop - start),
		(ctx.width, stop),

		# Destination Point
		(0, 0),
	)

def stop_relative_delete(ctx, start, stop):
	"""
	# Copy the lines above &start down next to &stop.

	# (illustration)`[||||start | stop||||] -> [>>||||xxx||||]`
	"""

	return ctx.replicate(
		(0, 0),
		(ctx.width, start),

		# Destination Point
		(0, (stop - start)),
	)

def update(rf, view, changes, *,
		len=len, min=min, max=max, sum=sum, list=list,
		isinstance=isinstance, enumerate=enumerate,
	):
	"""
	# Identify and render the necessary changes to update the view
	# and the corresponding display. The view's image and offset are adjusted
	# as the rendering instructions are compiled; if it is recognized
	# that the view's image is largely discarded or overwritten, a frame
	# refresh will be emitted instead of the incremental changes.

	# [ Engineering ]
	# The process is rather complicated as accuracy requires the translation
	# of line offsets in the past to where they are in the future. The
	# position of the view is also subject to this which means that much
	# filtering can only be performed after its final position is identified.

	# While difficult to measure, it is important that minimal effort is exerted here.
	# When large or complex changes are processed, it may be more efficient
	# to render a new image.
	"""

	# Future state; view.offset is current.
	visible = view.display.height
	start_of_view = rf.visible[0]
	end_of_view = start_of_view + visible
	total = len(rf.elements)

	# Reconstruct total so that view changes can be tracked as they were.
	dr = list(changes)
	dt = sum(r.change for r in dr)
	vt = total - dt

	updates = [] # Lines to update after view realignment.
	dimage = [] # Display (move) instructions to adjust for the delta.
	image_size = len(view.image)

	for r in dr:
		index = r.element or 0
		if isinstance(r, delta.Update):
			# Note updates for translating.
			updates.append(index)
			continue

		if image_size < 4:
			# When lines are inserted or removed,
			# Refresh when the remaining image is small.
			yield from refresh(rf, view, start_of_view)
			return

		vo = view.offset
		whence = index - vo
		ve = vo + visible

		if ve >= vt and vo > 0:
			# When on last page and first is not last.
			dins = stop_relative_insert
			ddel = stop_relative_delete
			last_page = True
		else:
			dins = start_relative_insert
			ddel = start_relative_delete
			last_page = False

		nd = len(r.deletion or ())
		ni = len(r.insertion or ())
		di = ni - nd
		# Identify the available lines before applying the change to &vt.
		limit = min(visible, vt)
		vt += di

		if di == 0:
			# No change in elements length.
			assert nd == ni
			updates.extend(range(index, index + ni))
			continue
		else:
			# Translate the indexes of past updates.
			# Transmit updates last in case the view's offset changes.
			for i, v in enumerate(updates):
				if index <= v:
					updates[i] += di

		if not isinstance(r, delta.Lines) or (index >= ve and not last_page):
			# Filter non-lines or out of scope changes.
			continue

		if nd:
			# Deletion

			if whence < 0:
				# Adjust view offset and identify view local deletion.
				d = max(0, whence + nd)
				w = 0
				if not last_page:
					view.offset -= (nd - d)
			else:
				assert whence >= 0
				w = whence
				d = min(nd, visible - whence)

			if last_page:
				view.offset -= nd
				# Apply prior to contraining &d to the available area.
				# In negative &whence cases, &view.offset has already
				# been adjusted for the changes before the view.
				if view.offset <= 0:
					# Delete caused transition.
					view.offset = 0
					s = view.delete(w, d)
					s = view.prefix(list(map(rf.render, rf.elements[0:d])))
					dimage.append(view.render(s))
					image_size -= d
					continue

			if d:
				# View local changes.
				s = view.delete(w, d)
				image_size -= d
				dimage.append((ddel(view.display, s.start, s.stop),))
		elif ni:
			# Insertion

			if last_page:
				view.offset += ni
				d = min(visible, ni)
			elif whence < 0:
				# Nothing but offset updates.
				view.offset += ni
				continue
			else:
				d = max(0, min(visible - whence, ni))

			s = view.insert(whence, d)
			dimage.append((dins(view.display, s.start, s.stop),))
			updates.extend(range(index, index+d))

			image_size -= d
		else:
			assert False # Never; continued at `di == 0`.
	else:
		# Initialize last_page for zero change cases.
		# Usually, scroll operations.
		ve = view.offset + visible
		if ve >= total and view.offset > 0:
			last_page = True
		else:
			last_page = False

	# After the deltas have been translated and enqueued

	dv = start_of_view - view.offset
	if abs(dv) >= visible or image_size < 4:
		# Refresh when scrolling everything out.
		yield from refresh(rf, view, start_of_view)
		return

	if dv:
		# Scroll view.
		if dv > 0:
			# View's position is before the refraction's.
			# Advance offset after aligning the image.
			view.delete(0, dv)
			view.offset += dv
			dimage.append([scroll_forward(view.display, dv)])
		else:
			# View's position is beyond the refraction's.
			# Align the image with prefix.
			s = view.prefix(list(map(rf.render,
				rf.elements[start_of_view:start_of_view-dv]
			)))
			view.trim()
			dimage.append([scroll_backward(view.display, -dv)] + list(view.render(s)))

	# Trim or Compensate
	displayed = len(view.image)
	available = min(visible, total)
	if displayed > visible:
		# Trim.
		view.trim()
		dimage.append(view.compensate())
	elif displayed < available:
		if last_page:
			stop = start_of_view + (available - displayed)
			s = view.prefix(list(map(rf.render, rf.elements[start_of_view:stop])))
			view.offset += s.stop - s.start
			dimage.append(view.render(s))
		else:
			tail = start_of_view + displayed
			stop = start_of_view + available
			s = view.suffix(list(map(rf.render, rf.elements[tail:stop])))
			dimage.append(view.render(s))

		# Pad with Empty if necessary.
		yield from view.compensate()

	# Transmit delta.
	for x in dimage:
		yield from x

	# Update line in view.
	for lo in updates:
		# Translated line indexes. (past to present)
		if lo >= start_of_view and lo < end_of_view:
			yield from render(rf, view, lo)

def refresh(rf:types.Refraction, view:types.View, whence:int):
	"""
	# Overwrite &view.image with the elements in &rf
	# starting at the absolute offset &whence.

	# The &view.offset is updated to &whence, but &rf.visibility is presumed
	# to be current.
	"""

	visible = view.display.height
	phrases = list(map(rf.render, rf.elements[whence:whence+visible]))
	pad = visible - len(phrases)
	if pad > 0:
		phrases.extend([view.Empty] * pad)
	view.update(slice(0, visible), phrases)
	view.trim()
	view.offset = whence

	return view.render(slice(0, visible))
