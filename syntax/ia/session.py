"""
# Session and device instructions.
"""
from . import types
event, Index = types.Index.allocate('session')

@event('close')
def close_session(session, frame, rf, event):
	"""
	# Exit the process.
	"""

	raise SystemExit(0)

@event('save')
def save_session_snapshot(session, frame, rf, event):
	"""
	# Serialize a snapshot of the session to a file on disk.
	"""

	session.store()

@event('reset')
def load_session_snapshot(session, frame, rf, event):
	"""
	# Serialize a snapshot of the session to a file on disk.
	"""

	session.load()
	session.reframe(0)

@event('cancel')
def cancel(session, frame, rf, event):
	"""
	# Refocus the subject refraction and reset any location area state.
	"""

	session.keyboard.set('control')
	session.dispatch_delta(session.focus.cancel())

@event('screen', 'refresh')
def screen_refresh(session, frame, rf, event, *, quantity=1):
	frame.refresh()

	if session.device.quantity() > 0:
		session.dispatch_delta(frame.render(session.device.screen))

@event('screen', 'resize')
def screen_resize(session, frame, rf, event, *, quantity=1):
	session.resize()

@event('resource', 'relocate')
def s_open_resource(session, frame, rf, event):
	"""
	# Navigate to the resource location.
	"""

	frame.relocate((frame.vertical, frame.division))

@event('resource', 'save')
def s_update_resource(session, frame, rf, event):
	"""
	# Update the resource to reflect the refraction's element state.
	"""

	frame.rewrite((frame.vertical, frame.division))

@event('resource', 'write')
def s_write_resource(session, frame, rf, event):
	"""
	# Update the resource to reflect the refraction's element state
	# without confirmation.
	"""

	session.save_resource(rf.origin.ref_path, rf.elements)

@event('resource', 'clone')
def s_clone_resource(session, frame, rf, event):
	"""
	# Write the elements to the resource identified by the absolute path in
	# device's text.
	"""

	url = session.device.transfer_text()
	if url.startswith('/'):
		re = rf.origin.ref_path@url
	else:
		raise ValueError("not a filesystem path: " + url)

	session.save_resource(re, rf.elements)

@event('resource', 'close')
def s_close_resource(session, frame, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.close_resource(rf.origin.ref_path)
	session.chresource(frame, rf.origin.ref_path@'/dev/null')
	session.keyboard.set('control')
	frame.refocus()

@event('resource', 'reload')
def s_reload_resource(session, frame, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.close_resource(rf.origin.ref_path)
	session.chresource(frame, rf.origin.ref_path)
	session.keyboard.set('control')
	frame.refocus()

@event('resource', 'open')
def s_open_resource(session, frame, rf, event):
	"""
	# Open the resource identified by the transferred text.
	"""

	url = session.device.transfer_text()
	empty, path = url.split('file://')
	session.chresource(frame, rf.origin.ref_path@(path.strip()))
	session.keyboard.set('control')
	frame.refocus()

@event('frame', 'create')
def frame_create(session, frame, rf, event):
	"""
	# Create and focus a new session frame.
	"""

	session.reframe(session.allocate())

@event('frame', 'clone')
def frame_clone(session, frame, rf, event):
	"""
	# Copy the &frame and focus its new instance.
	"""

	fi = session.allocate()
	session.frames[fi].fill(frame.refractions)
	session.frames[fi].refresh()
	session.reframe(fi)

@event('frame', 'close')
def frame_close(session, frame, rf, event):
	"""
	# Close the current frame leaving resources open within the session.
	"""

	assert frame.index == session.frame
	session.release(session.frame)

@event('frame', 'previous')
def frame_switch_previous(session, frame, rf, event):
	"""
	# Select and focus the next frame in the session.
	"""

	session.reframe(session.frame - 1)

@event('frame', 'next')
def frame_switch_next(session, frame, rf, event):
	"""
	# Select and focus the next frame in the session.
	"""

	session.reframe(session.frame + 1)

@event('frame', 'switch')
def frame_switch(session, frame, rf, event):
	"""
	# Select and focus the next frame in the session.
	"""

	session.reframe(session.device.quantity() - 1)

@event('elements', 'transmit')
def transmit_selected_elements(session, frame, rf, event):
	"""
	# Send the selected elements to the device manager.
	"""

	if rf.focus[0].magnitude > 0:
		# Vertical Range
		start, position, stop = rf.focus[0].snapshot()
		selection = '\n'.join(rf.elements[start:stop])
	else:
		# Horizontal Range
		ln = rf.focus[0].get()
		start, position, stop = rf.focus[1].snapshot()
		selection = rf.elements[ln][start:stop]
	session.device.transmit(selection.encode('utf-8'))

@event('synchronize')
def synchronize_io(session, *eventcontext):
	"""
	# Respond to an I/O synchronization event for integrating
	# parallel I/O events into the terminal application.
	"""

	session.integrate(*eventcontext)
