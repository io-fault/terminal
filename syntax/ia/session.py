"""
# Session and device instructions.
"""
from . import types
event, Index = types.Index.allocate('session')

@event('screen', 'refresh')
def screen_refresh(session, rf, event, *, quantity=1):
	session.refresh(session.device.quantity())

@event('screen', 'resize')
def screen_resize(session, rf, event, *, quantity=1):
	session.resize()

@event('resource', 'relocate')
def s_open_resource(session, rf, event):
	"""
	# Navigate to the resource location.
	"""

	session.relocate((session.vertical, session.division))

@event('resource', 'save')
def s_update_resource(session, rf, event):
	"""
	# Update the resource to reflect the refraction's element state.
	"""

	session.rewrite((session.vertical, session.division))

@event('resource', 'write')
def s_write_resource(session, rf, event):
	"""
	# Update the resource to reflect the refraction's element state
	# without confirmation.
	"""

	session.save_resource(rf.origin.ref_path, rf.elements)

@event('resource', 'clone')
def s_clone_resource(session, rf, event):
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
def s_close_resource(session, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.close_resource(rf.origin.ref_path)
	session.chresource(session.vertical, session.division, rf.origin.ref_path@'/dev/null')
	session.keyboard.set('control')
	session.refocus()

@event('resource', 'reload')
def s_reload_resource(session, rf, event):
	"""
	# Remove the resource from the session releasing any associated memory.
	"""

	session.close_resource(rf.origin.ref_path)
	session.chresource(session.vertical, session.division, rf.origin.ref_path)
	session.keyboard.set('control')
	session.refocus()

@event('resource', 'open')
def s_open_resource(session, rf, event):
	"""
	# Open the resource identified by the transferred text.
	"""

	url = session.device.transfer_text()
	empty, path = url.split('file://')
	session.chresource(session.vertical, session.division, rf.origin.ref_path@(path.strip()))
	session.keyboard.set('control')
	session.refocus()
