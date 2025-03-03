from functools import partial

class Index(object):
	"""
	# Instruction index for methods.
	"""

	def __init__(self, category, parameters):
		self.i_storage = {}
		self.i_parameters = parameters
		self.i_category = category

	@classmethod
	def allocate(Class, category, *parameters):
		c = Class(category, parameters)
		return c.define, c

	def define(self, *path, **kw):
		def update(method, Index=self):
			Index.i_storage[path] = method
			return method
		return update

	def partial(self, method, resource, *, P=partial):
		return P(method, resource, *[
			getattr(resource, p) for p in self.i_parameters
		])

	def select(self, path):
		return self.i_storage[path]

class Mode(object):
	"""
	# A mapping of user events to application events.

	# [ Elements ]
	# /default/
		# The default action to translate events into.
	# /mapping/
		# The Application Event to User Event index.
	# /reverse/
		# The User Event to Application Event index.
	"""

	def __init__(self, default=None):
		self.default = default
		self.mapping = dict()
		self.reverse = dict()

	def assign(self, keybind, category, action, parameters = ()):
		"""
		# Assign the character sequence to action.
		"""

		ikey = (category, action, parameters)
		if ikey not in self.mapping:
			self.mapping[ikey] = set()

		self.mapping[ikey].add(keybind)
		self.reverse[keybind] = ikey

	def event(self, kb):
		"""
		# Return the action associated with the given key.
		"""

		return self.reverse.get(kb, self.default)

# XXX: Adjust Selection and Mode to support intercepts for temporary bindings.
# The binding for return is overloaded and to eliminate
# the internal switching(routing to Refraction.activate), a trap needs to be
# employed so that open/save activation may be performed when the location bar is active.
# `Session.input.intercept(mode, ReturnKey, location.open|location.save)` where open, save and
# cancel clears the intercept.
class Selection(object):
	"""
	# A mapping of &Mode instances controlling the current application event translation mode.

	# [ Elements ]
	# /index/
		# The collection of &Mode instances assigned to their identifier.
	# /current/
		# The &Mode in &index that is currently selected.
	# /last/
		# The previous &Mode identifier.
	# /redirects/
		# The event translation that occurs when the selection state
		# is under a qualified mode.
	"""

	@property
	def mapping(self):
		"""
		# Get the currently selected mapping by the defined name.
		"""

		return self.current[0]

	@classmethod
	def standard(Class):
		return Class(standard)

	def __init__(self, index):
		self.index = index
		self.current = None
		self.last = None
		self.redirections = {}
		self.qualification = None
		self.data = None

	def reset(self, mode):
		self.set(mode)
		self.last = self.current
		self.qualification = None

	def revert(self):
		"""
		# Swap the selected mode to &last.
		"""

		self.current, self.last = self.last, self.current

	def set(self, name):
		self.last = self.current
		self.current = (name, self.index[name])
		return self.current

	def mode(self, name):
		"""
		# Whether the given mode, &name, is currently active.
		"""
		return self.current[0] == name

	def qualify(self, qid):
		"""
		# Update the qualification.
		"""

		self.qualification = qid

	def event(self, key):
		"""
		# Look up the event using the currently selected mapping.
		"""

		return (self.current[0], self.current[1].event(key))

	def redirect(self, event):
		prefix = event[:2]
		re = self.redirections[self.qualification].get(prefix, prefix)
		return re + (event[2],)

	def interpret(self, event):
		"""
		# Route the event to the target given the current processing state.
		"""

		mapping, operation = self.event(event)
		if operation is None:
			return (None, ('meta', ('ineffective',), ()))
		if self.qualification is not None:
			operation = self.redirect(operation)
			self.qualification = None

		return (mapping, operation)
