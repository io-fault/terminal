"""
# Input state control and transformations(distribution).
"""
from . import types
event, Index = types.Index.allocate('meta')

@event('ineffective')
def operation_not_found(session, rf, event):
	"""
	# No operational effect.

	# Used when an event could not be mapped to an operation.
	"""
	pass

@event('terminal', 'focus', 'acquire')
def application_focused(session, rf, event):
	"""
	# Received explicit focus in event.
	"""
	pass

@event('terminal', 'focus', 'release')
def application_switched(session, rf, event):
	"""
	# Received explicit focus out event.
	"""
	pass

@event('transition', 'capture', 'replace')
def transition_capture_replace(session, rf, event):
	"""
	# Prepare to replace the character at the cursor with a capture.
	"""

	session.keyboard.set('capture-replace')

@event('transition', 'capture', 'insert')
def transition_capture_insert(session, rf, event):
	"""
	# Prepare to insert a captured character at the cursor.
	"""

	session.keyboard.set('capture-insert')

@event('view', 'refresh')
def refresh_view_image(session, rf, event):
	"""
	# Redraw the view's image.
	"""

	from .. import projection
	view = session.view
	session.log(
		f"View: {view.offset!r} {view.version!r} {view.display.dimensions!r}",
		f"Cursor: {rf.focus[0].snapshot()!r}",
		f"Refraction: {rf.visibility[0].snapshot()!r}",
		f"Lines: {len(rf.elements)}, {rf.log.snapshot()}",
	)
	session.send(*projection.refresh(rf, view, rf.visible[0]))

@event('select', 'distributed', 'operation')
def set_distributing(session, rf, event):
	"""
	# Select distributed operations.
	"""

	session.keyboard.qualify('distributed')

@event('transition')
def atposition_insert_mode_switch(session, rf, event):
	"""
	# Transition into insert-mode.
	"""

	session.keyboard.set('insert')

@event('transition', 'start-of-field')
def fieldend_insert_mode_switch(session, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the start
	# of the horizontal range.
	"""

	rf.focus[1].move(0, +1)
	session.keyboard.set('insert')

@event('transition', 'end-of-field')
def fieldend_insert_mode_switch(session, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the end
	# of the horizontal range.
	"""

	rf.focus[1].move(0, -1)
	session.keyboard.set('insert')

@event('transition', 'start-of-line')
def startofline_insert_mode_switch(session, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the beginning of the line.
	"""

	ln = rf.focus[0].get()
	i = 0
	for i, x in enumerate(rf.elements[ln]):
		if x != '\t':
			break
	rf.focus[1].set(i)
	session.keyboard.set('insert')

@event('transition', 'end-of-line')
def endofline_insert_mode_switch(session, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the end of the line.
	"""

	ln = rf.focus[0].get()
	rf.focus[1].set(len(rf.elements[ln]))
	session.keyboard.set('insert')

@event('session', 'suspend')
def pause(session, rf, event):
	"""
	# Place the process in the background.
	"""
	session.suspend()
