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

restricted = {}
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

def override_dimensions(terminal, dimensions):
	if None in dimensions:
		real = (terminal.width, terminal.height)
		return (
			dimensions[0] or real[0],
			dimensions[1] or real[1],
		)
	else:
		return dimensions

def configure_frame(executable, options, sources):
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
	init = [wd@x for x in sources]

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
	}

	sources = recognition.merge(
		config, recognition.legacy(restricted, required, inv.argv),
	)

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

	# sys.terminaldevice
	editor = elements.Session(path, types.Device())

	def klog(*lines, depth=[0], elog=editor.log):
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

	if config['working-directory'] is None:
		wd = config['working-directory'] = process.fs_pwd()
	else:
		wd = config['working-directory'] = files.root@config['working-directory']
		process.fs_chdir(wd)

	divisions, rfq = configure_frame(path, config, sources)

	try:
		editor.focus.remodel(editor.device.screen.area, divisions)
		editor.focus.fill(map(editor.refract, rfq))
		editor.focus.refresh()

		editor.log("Device: " + (config.get('interface-device') or "unspecified"))
		editor.log("Working Directory: " + str(process.fs_pwd()))
		editor.log("Path Arguments:", *['\t' + s for s in sources])
		editor.refocus()
		editor.dispatch_delta(editor.focus.render(editor.device.screen))
		editor.device.update_frame_list("Frame 1")
		editor.device.update_frame_status(0, 0)

		while editor.frames:
			editor.cycle()
	finally:
		pass
