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
