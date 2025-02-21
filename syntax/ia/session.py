"""
# Session and device instructions.
"""
from .types import Index
event, Index = Index.allocate('session')

@event('log')
def open_session_log(session, frame, rf, event):
	"""
	# Attach the session transcript to the selected division.
	"""

	from ..elements import Refraction
	sd = frame.chresource((frame.vertical, frame.division), Refraction(session.transcript))
	session.dispatch_delta(sd)

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

	frame.relocate(session, (frame.vertical, frame.division))

@event('resource', 'save')
def s_update_resource(session, frame, rf, event):
	"""
	# Update the resource to reflect the refraction's element state.
	"""

	frame.rewrite(session, (frame.vertical, frame.division))

@event('resource', 'write')
def s_write_resource(session, frame, rf, event):
	"""
	# Update the origin's content to reflect the element state of &rf.source.
	"""

	session.store_resource(rf.source)

@event('resource', 'copy')
def copy_resource(session, frame, rf, event):
	"""
	# Write the elements to the resource identified by the absolute path in
	# the device's transferred text.

	# Used when the device manager passes the path in after the user selects
	# a destination path.
	"""

	url = session.device.transfer_text()
	if not url.startswith('/'):
		raise ValueError("not a filesystem path: " + url) # Expects an absolute path.

	re = rf.source.origin.ref_path@url
	src = session.allocate_resource(session.reference(re))
	src.elements = rf.source.elements
	src.encoding = rf.source.encoding
	if src.origin.ref_path.fs_type() != 'void':
		src.status = src.origin.ref_path.fs_status()

	session.store_resource(src)

@event('resource', 'close')
def s_close_resource(session, frame, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.delete_resource(rf.source)
	devnull = rf.source.origin.ref_path@'/dev/null'
	session.chresource(frame, devnull)
	session.keyboard.set('control')
	frame.refocus()

@event('resource', 'reload')
def s_reload_resource(session, frame, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.delete_resource(rf.source)
	session.chresource(frame, rf.source.origin.ref_path)
	session.keyboard.set('control')
	frame.refocus()

@event('resource', 'switch')
def s_open_resource(session, frame, rf, event):
	"""
	# Open the resource identified by the transferred text.
	"""

	url = session.device.transfer_text()
	empty, path = url.split('file://')
	session.chresource(frame, rf.source.origin.ref_path@(path.strip()))
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
		selection = rf.forms.lf_lines.sequence(rf.vertical_selection_text())
	else:
		selection = rf.horizontal_selection_text()
	session.device.transmit(selection.encode('utf-8'))
