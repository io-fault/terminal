from .. import sequence as module

def test_Segments(test):
	"""
	# - &module.Segments
	"""
	s = module.Segments()
	l = [
		('line1',),
		('line2',),
		('line3',),
	]
	s.insert(0, l)

	l2 = [
		('segment2-line1',),
		('segment2-line2',),
	]
	s.insert(0, l2)
	test/s[:] == (l2 + l)
	test/s[:2] == l2
	test/s[:3] == l2 + l[:1] # crosses over
	test/s[1:3] == l2[1:] + l[:1] # crosses over

	s.partition()
	test/s[:] == (l2 + l)
	test/s.sequences == [l2 + l]

	s.clear()
	test/s[:] == []

	s[0:0] = l
	test/s[:] == l

def test_Segments_Sequence_Interface(test):
	"""
	# - &module.Segments
	"""
	l = list(range(1057))
	s = module.Segments(l) # Instantiation needs to act like list()
	test/len(s) == 1057
	test/list(s[:]) == l

	s[3:3] = [4,3,2]
	l[3:3] = [4,3,2]
	test/list(s[:]) == l

	seqs = (l, s)

	for x in seqs:
		x[4:8] = x[22:26]

	test/seqs[0] == list(seqs[1])

	test/seqs[0][1000:1200] == seqs[1][1000:1200]

def test_Segments_select(test):
	# iterator interface to arbitrary slice
	seg = module.Segments(list(range(439)))
	test/list(seg.select(400, 445)) == list(range(400, 439))

if __name__ == '__main__':
	from ...test import library as libtest
	import sys; libtest.execute(sys.modules[__name__])
