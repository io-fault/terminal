from ...syntax import types as module

def test_Model_set_margin_size(test):
	"""
	# - &module.Model.set_margin_size
	"""

	m = module.Model()
	m.configure(module.Area(0, 0, 100, 100), [(1, 1, )])

	test/m.set_margin_size(0, 0, 3, 3) == 3
	test/m.fm_deltas[(0,0,3)] == 3

	test/m.set_margin_size(0, 0, 3, 2) == -1
	test/m.fm_deltas[(0,0,3)] == 2

	test/m.set_margin_size(0, 0, 3, 10) == 8
	test/m.fm_deltas[(0,0,3)] == 10

def test_System_variant(test):
	"""
	# - &module.System.variant

	# Validate that the variant method tolerates differences in the title.
	"""

	s1 = module.System('m', 'c', 'a', 'i', 'title-1')
	s2 = module.System('m', 'c', 'a', 'i', 'title-2')
	test/s1 != s2
	test/s2.variant(s1) == True

	# Same title as s2, but a different system (environment).
	ds = [
		module.System('dm', 'c', 'a', 'i', 'title-2'),
		module.System('m', 'dc', 'a', 'i', 'title-2'),
		module.System('m', 'c', 'da', 'i', 'title-2'),
		module.System('m', 'c', 'a', 'di', 'title-2'),
	]
	for s3 in ds:
		test/s3.variant(s1) == False
		test/s3.variant(s2) == False

def test_Reference_string(test):
	"""
	# - &module.Reference.__str__
	"""

	sys = module.System(
		"system", "user", "token", "host", "title"
	)
	ref = module.Reference(sys, 'type', 'verbatum-path', None, "/ref/file", {})
	test/str(ref) == "system://user:token@host[title]/ref/file"
