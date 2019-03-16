"""
# Core structures tests.
"""
from .. import core as library

def test_Point(test):
	"""
	# - &library.Point
	"""

	# Sanity
	p0 = library.Point((0,0))
	p1 = library.Point((1,1))
	p2 = library.Point((2,2))
	p3 = library.Point((5,6))
	test/(p1+p0) == p1
	test/(p1-p0) == p1
	test/(p2-p0) == p2
	test/(p2-p1) == p1
	test/(p2+p1) == (3,3)
	test/(p2+p1) == (3,3)
	test/(p3+p0) == p3
	test/(p3+p1) == (6,7)
	test/(p3-p1) == (4,5)

def test_Position(test):
	"""
	# Check all the methods of &library.Position
	"""
	p = library.Position()
	test/p.snapshot() == (0,0,0)
	test/p.get() == 0

	# checking corner cases
	p.update(2)
	test/p.snapshot() == (0,2,0)

	# above magnitude
	test/p.relation() == 1

	test/p.contract(0, 2)
	test/p.maximum == -2
	test/p.relation() == 1
	test/p.get() == 0 # contract offset was at zero
	test/p.minimum == 0

	p.configure(10, 10, 5)
	test/p.relation() == 0
	test/p.get() == 15
	test/p.maximum == 20
	test/p.minimum == 10

	p.move(5, -1)
	test/p.get() == 15

	p.move(4, -1)
	test/p.get() == 16

	p.move(3, -1)
	test/p.get() == 17

	p.move(0, -1)
	test/p.get() == 20

	p.move(0, 1)
	test/p.get() == 10

	p.move(1, 1)
	test/p.get() == 11

	p.move(1, 0)
	test/p.get() == 12

	p.move(1)
	test/p.get() == 13

	p.update(-1)
	test/p.get() == 12

	p.update(1)
	test/p.get() == 13

	p.update(-4)
	test/p.get() == 9 # before datum
	test/p.relation() == -1

	p.contract(0, 1)
	test/p.relation() == -1
	test/p.get() == 8 # still before datum
	test/p.offset == -2
	test/p.magnitude == 9
	test/p.snapshot() == (10, 8, 19)

if __name__ == '__main__':
	import sys; from fault.test import library as libtest
	libtest.execute(sys.modules[__name__])

