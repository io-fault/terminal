from . import types
event, Index = types.Index.allocate('transaction')

@event('abort')
def xact_abort(r, event):
	r.abort()

@event('commit')
def xact_commit(r, event):
	r.commit()

@event('undo')
def log_undo(self, event, quantity = 1):
	self.undo(quantity)

@event('redo')
def log_redo(self, event, quantity = 1):
	self.redo(quantity)

@event('checkpoint')
def log_checkpoint(self, event):
	self.checkpoint()
