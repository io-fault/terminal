from .. import fields as module

def test_sequence(test):
	return
	s = module.Sequence()
	f = module.Field()
	s.insert(f)

	test/s.length() == 0

	test/list(s.value()) == [(f, (s,))]

	s.clear()
	test/tuple(s.value()) == ()
	test/s.length() == 0
	test/s.position.get() == 0

	s.insert(f)

	test/s.find(0) == None
	test/s.offset(f) == (0, 0, 0)
	test/list(s.value()) == [(f, (s,))]
	test/s.length() == 0

	f.insert("test")
	test/s.length() == 4

	test/s.find(0) == f
	test/s.find(1) == f
	test/s.find(2) == f
	test/s.find(3) == f
	test/s.find(4) == None

	f2 = module.Field()
	s.insert(f2)
	test/list(s.value()) == [(f, (s,)), (f2, (s,))]

	f2.insert(".")
	test/str(s) == "test."
	test/s.find(4) == f2

	# position is at end
	test/s.offset(f) == (0, 4, 4)
	f.move(0, 1)
	test/s.offset(f) == (0, 0, 4)

	test/s.offset(f2) == (4, 5, 5)
	s.move(1, 1)
	test/s.selection == f2
	s.move(1)
	test/s.selection == None # position at edge

	f3 = module.Field()
	s.insert(f3)
	f3.insert("fields")
	test/str(s) == "test.fields"
	test/list(s.value()) == [(f, (s,)), (f2, (s,)), (f3, (s,))]

doc = """import foo
import bar
import nothing

def function(a, b):
	pass

class Class():

	def __init__(self):
		pass
		pass
		if 0:
			pass
		pass
"""

def test_block(test):
	return
	lines = [module.Sequence(module.parse(line)) for line in doc.split('\n')]

	# contiguous
	start, stop = module.block(lines, 1, 0, len(lines), module.indentation_block)
	test/start == 0
	test/stop == 2

	start, stop = module.block(lines, 12, 0, len(lines), module.indentation_block)
	test/start == 9
	test/stop == len(lines)

if __name__ == '__main__':
	from fault.development import libtest
	import sys; libtest.execute(sys.modules[__name__])
