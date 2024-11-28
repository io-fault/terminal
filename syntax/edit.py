"""
# Edit the syntax of files inside of a terminal environment.
"""
import os
import sys
import functools
import itertools
import weakref
import collections
from collections.abc import Mapping, Sequence, Iterable

from fault.vector import recognition
from fault.system import process
from fault.system import files
from fault.system.query import home

# Disable signal exits for multiple interpreter cases.
process.__signal_exit__ = (lambda x: None)

from . import types
from . import elements
from .system import IO

def fkrt(inv:process.Invocation) -> process.Exit:
	"""
	# &fault.kernel runtime entry point.
	"""
	import signal
	from fault.kernel import system

	# Block terminal stops as kqueue or signalfd will need to hear them.
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)

	system.dispatch(inv, Executable(Session(exe, terminal).setup))
	system.control()

restricted = {
	'--session': ('field-replace', True, 'session-sources'),
}
restricted.update(
	('-' + str(i), ('sequence-append', i, 'vertical-divisions'))
	for i in range(1, 10)
)
required = {
	'--device': ('field-replace', 'interface-device'),
	'-D': ('field-replace', 'working-directory'),
	'-S': ('set-add', 'excluded-session-status'),
	'-T': ('sequence-append', 'syntax-types'),

	'-x': ('field-replace', 'horizontal-position'),
	'-y': ('field-replace', 'vertical-position'),
	'-X': ('field-replace', 'horizontal-size'),
	'-Y': ('field-replace', 'vertical-size'),
}

def configure_frame(directory, executable, options, sources):
	"""
	# Apply configuration &options and load initial &sources for the &editor &Session.
	"""

	excluding = options['excluded-session-status']
	xy = (options['horizontal-position'], options['vertical-position'])
	hv = (options['horizontal-size'], options['vertical-size'])

	# NOTE: Currently ignored.
	position = tuple(x-1 for x in map(int, xy))
	dimensions = tuple(int(x) if x is not None else None for x in hv)

	model = (tuple(map(int, options['vertical-divisions'])) or (1, 1, 2))
	ndiv = sum(x or 1 for x in model)

	# Sources from command line. Follow with session status views and
	# a fill of /dev/null refractions between. Transcript is fairly
	# important right now, so force it in if there is space.
	init = [directory@x for x in sources]

	end = [
		executable/x
		for x in ('transcript',)
		if x not in excluding
	]
	# Exclude if there's only one division.
	end = end[:max(0, ndiv - 1)]

	nullcount = max(0, (ndiv - len(init) - len(end)))
	rfq = itertools.chain(
		init[:ndiv-len(end)],
		itertools.repeat(files.root@'/dev/null', nullcount),
		end,
	)

	return model, rfq

def configure_log_builtin(session):
	def klog(*lines, depth=[0], elog=session.log):
		if depth[0] > 0:
			# No logging while logging.
			return
		else:
			depth[0] += 1
			try:
				elog(*lines)
			finally:
				depth[0] -= 1
	import builtins
	builtins.log = klog

def configure_working_directory(config):
	if config['working-directory'] is None:
		wd = config['working-directory'] = process.fs_pwd()
	else:
		wd = config['working-directory'] = files.root@config['working-directory']
		process.fs_chdir(wd)
	return wd

def identify_executable(inv):
	from fault.system.query import executables as qexe

	exepath = str(inv.parameters['system']['name'])
	if exepath[:1] != '/':
		for executable in qexe(exepath):
			path = executable
			break
		else:
			# Unrecognized origin.
			path = files.root@'/var/empty/sy'
	else:
		path = files.root@exepath

	return path

def main(inv:process.Invocation) -> process.Exit:
	config = {
		'interface-device': None,
		'working-directory': None,
		'syntax-types': [],
		'vertical-divisions': [],
		'excluded-session-status': set(),

		'horizontal-position': '1',
		'vertical-position': '1',
		'horizontal-size': None,
		'vertical-size': None,
		'session-sources': False,
	}

	sources = recognition.merge(
		config, recognition.legacy(restricted, required, inv.argv),
	)

	path = identify_executable(inv)
	wd = configure_working_directory(config)
	device = types.Device()
	editor = elements.Session(IO.allocate(device.synchronize_io), path, device)
	configure_log_builtin(editor)

	fi = 0
	session_file = None
	if config['session-sources']:
		if not sources:
			sources.append(str(home()/'.syntax/Frames'))
		session_file = sources[-1]

		from .session import structure_frames as parse
		for sf in sources:
			with open(sf) as f:
				fspecs = parse(f.read())

			try:
				editor.restore(fspecs)
			except:
				pass
		else:
			# Clear source list for fallback case of an empty session.
			sources = []

	# Create frame if not session sourced or the session was empty.
	if not editor.frames or not config['session-sources']:
		layout, rfq = configure_frame(wd, path, config, sources)
		fi = editor.allocate(layout = layout)
		editor.frames[fi].fill(map(editor.refract, rfq))

	editor.reframe(fi)
	editor.log("Factor: " + __name__)
	editor.log("Device: " + (config.get('interface-device') or "manager default"))
	editor.log("Working Directory: " + str(wd))
	if sources:
		editor.log("Path Arguments:", *['\t' + s for s in sources])

	# System I/O loop for command substitution and file I/O.
	editor.io.dispatch_loop()

	try:
		while editor.frames:
			editor.cycle()
	finally:
		if session_file is not None:
			from .session import sequence_frames as seq
			with open(session_file, 'w') as f:
				f.write(seq(editor.snapshot()))
