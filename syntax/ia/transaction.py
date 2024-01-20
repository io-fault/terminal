"""
# &.types.Refraction.log operations.
"""
from . import types
event, Index = types.Index.allocate('transaction')

from .. import delta

@event('abort')
def xact_abort(session, rf, event):
	"""
	# Retract until the last checkpoint and enter control mode..
	"""
	rf.log.undo(rf.elements)
	session.keyboard.set('control')

@event('commit')
def xact_commit(session, rf, event):
	"""
	# Log a checkpoint and enter control mode.
	"""
	rf.log.checkpoint()
	session.keyboard.set('control')

@event('undo')
def log_undo(session, rf, event, quantity=1):
	"""
	# Retract until the last checkpoint and move the records to the future.
	"""
	rf.log.undo(rf.elements, quantity)

@event('redo')
def log_redo(session, rf, event, quantity=1):
	"""
	# Apply future until the next checkpoint and move the records to the past.
	"""
	rf.log.redo(rf.elements, quantity)
