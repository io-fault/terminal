"""
# Input state control and transformations(distribution).
"""
from .. import annotations
from . import types
event, Index = types.Index.allocate('meta')

@event('synchronize')
def synchronize_io(session, *eventcontext):
	"""
	# Respond to an I/O synchronization event for integrating
	# parallel I/O events into the terminal application.
	"""

	session.integrate(*eventcontext)

@event('ineffective')
def operation_not_found(session, frame, rf, event):
	"""
	# No operational effect.

	# Used when an event could not be mapped to an operation.
	"""

	pass

@event('terminal', 'focus', 'acquire')
def application_focused(session, frame, rf, event):
	"""
	# Received explicit focus in event.
	"""

	pass

@event('terminal', 'focus', 'release')
def application_switched(session, frame, rf, event):
	"""
	# Received explicit focus out event.
	"""

	pass

def perform_selected_action(session, frame, rf, event, hold=False):
	if rf.activate is not None:
		action = rf.activate
		r = action(session, frame, rf, event)
		if not hold:
			session.dispatch_delta(frame.cancel())
			session.keyboard.set('control')
		return r
	elif session.keyboard.mapping == 'insert':
		# Presume document editing.
		return session.events['delta'](('open', 'ahead'))(session, frame, rf, event)
	elif session.keyboard.mapping == 'control':
		return session.events['navigation'](('horizontal', 'forward', 'end'))(session, frame, rf, event)

@event('activate')
def execute_and_cancel(session, frame, rf, event):
	"""
	# Perform the primary action of the target refraction and cancel the prompt.
	"""

	return perform_selected_action(session, frame, rf, event)

@event('activate', 'continue')
def execute_and_hold(session, frame, rf, event):
	"""
	# Perform the primary action and maintain the prompt's focus.
	"""

	return perform_selected_action(session, frame, rf, event, hold=True)

@event('query')
def directory_annotation_request(session, frame, rf, event):
	"""
	# Construct and display the default directory annotation
	# for the Refraction's syntax type or &.types.Annotation.rotate
	# the selection if an annotation is already present.
	"""

	q = rf.annotation
	if q is not None:
		q.rotate()
	else:
		# Configure annotation based on syntax type.
		pass

for i, (rb, ri) in enumerate(annotations.integer_representations):
	def int_annotation(session, frame, rf, event, *, index=i):
		rf.annotate(annotations.BaseAnnotation(rf.focus[1], index=index))
		session.keyboard.revert()
	event('integer', 'select', rb)(int_annotation)

for i, (rb, ri) in enumerate(annotations.codepoint_representations):
	def cp_annotation(session, frame, rf, event, *, index=i):
		rf.annotate(annotations.CodepointAnnotation(rf.focus[1], index=index))
		session.keyboard.revert()
	event('codepoint', 'select', rb)(cp_annotation)

@event('integer', 'color', 'swatch')
def color_annotation(session, frame, rf, event):
	rf.annotate(annotations.ColorAnnotation(rf.focus[1]))
	session.keyboard.revert()

@event('status')
def status_annotation(session, frame, rf, event):
	rf.annotate(annotations.Status('', session.keyboard, rf.focus))
	session.keyboard.revert()

@event('transition', 'annotation', 'void')
def transition_no_such_annotation(session, frame, rf, event):
	"""
	# Restore the mode to the previous selection and clear the annotation.
	"""

	rf.annotate(None)
	session.keyboard.revert()

@event('annotation', 'rotate')
def annotation_rotate(session, frame, rf, event, *, quantity=1):
	"""
	# Change the image of the annotation using its rotate interface.
	"""

	if rf.annotation is not None:
		rf.annotation.rotate(quantity)

@event('transition', 'annotations', 'select')
def transition_capture_insert(session, frame, rf, event):
	"""
	# Prepare to select an annotation.
	"""

	rf.annotate(annotations.Status('view-select', session.keyboard, rf.focus))
	session.keyboard.set('annotations')

@event('transition', 'exit')
def transition_last_mode(session, frame, rf, event):
	"""
	# Restore the mode to the previous selection.
	"""

	session.keyboard.revert()

@event('transition', 'insert', 'cursor')
def atposition_insert_mode_switch(session, frame, rf, event):
	"""
	# Transition into insert-mode.
	"""

	rf.source.checkpoint()

	session.keyboard.set('insert')
	rf.whence = 0

@event('transition', 'insert', 'start-of-field')
def fieldend_insert_mode_switch(session, frame, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the start
	# of the horizontal range.
	"""

	rf.source.checkpoint()

	rf.focus[1].move(0, +1)
	session.keyboard.set('insert')
	rf.whence = -1

@event('transition', 'insert', 'end-of-field')
def fieldend_insert_mode_switch(session, frame, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the end
	# of the horizontal range.
	"""

	rf.source.checkpoint()

	rf.focus[1].move(0, -1)
	session.keyboard.set('insert')
	rf.whence = +1

@event('transition', 'insert', 'start-of-line')
def startofline_insert_mode_switch(session, frame, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the beginning of the line.
	"""

	rf.source.checkpoint()

	lo = rf.focus[0].get()
	rf.focus[1].set(rf.source.sole(lo).ln_level)
	session.keyboard.set('insert')
	rf.whence = -2

@event('transition', 'insert', 'end-of-line')
def endofline_insert_mode_switch(session, frame, rf, event):
	"""
	# Transition into insert-mode moving the cursor to the end of the line.
	"""

	rf.source.checkpoint()

	lo = rf.focus[0].get()
	ln = rf.source.sole(lo)
	rf.focus[1].set(ln.ln_length)
	session.keyboard.set('insert')
	rf.whence = +2

@event('transition', 'capture', 'replace')
def transition_capture_replace(session, frame, rf, event):
	"""
	# Prepare to replace the character at the cursor with a capture.
	"""

	session.keyboard.set('capture-replace')

@event('transition', 'capture', 'key')
def transition_capture_key(session, frame, rf, event):
	"""
	# Prepare to capture the key and modifiers of a stroke.
	"""

	session.keyboard.set('capture-key')

@event('transition', 'capture', 'insert')
def transition_capture_insert(session, frame, rf, event):
	"""
	# Prepare to insert a captured character at the cursor.
	"""

	session.keyboard.set('capture-insert')

@event('view', 'refresh')
def refresh_view_image(session, frame, rf, event):
	"""
	# Redraw the view's image.
	"""

	from .. import projection
	view = frame.view
	session.log(
		f"View: {view.offset!r} {view.version!r} {view.area!r}",
		f"Cursor: {rf.focus[0].snapshot()!r}",
		f"Refraction: {rf.visibility[0].snapshot()!r}",
		f"Lines: {rf.source.ln_count()}, {rf.source.version()}",
	)
	session.dispatch_delta(projection.refresh(rf, view, rf.visible[0]))

@event('select', 'distributed', 'operation')
def set_distributing(session, frame, rf, event):
	"""
	# Select distributed operations.
	"""

	session.keyboard.qualify('distributed')

@event('session', 'suspend')
def pause(session, frame, rf, event):
	"""
	# Place the process in the background.
	"""

	session.suspend()

@event('prepare', 'command')
def prompt(session, frame, rf, event):
	"""
	# Prepare the prompt for performing a system command.
	"""

	frame.prepare(session, "system", (frame.vertical, frame.division))
