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
from fault.system import query

# Disable signal exits for multiple interpreter cases.
process.__signal_exit__ = (lambda x: None)

from .. import configuration

from . import types
from . import elements
from .system import IOManager

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

def configure_frame(directory, executable, options):
	"""
	# Apply configuration &options for the session.
	"""

	excluding = options['excluded-session-status']
	xy = (options['horizontal-position'], options['vertical-position'])
	hv = (options['horizontal-size'], options['vertical-size'])

	# NOTE: Currently ignored.
	position = tuple(x-1 for x in map(int, xy))
	dimensions = tuple(int(x) if x is not None else None for x in hv)

	vd = options['vertical-divisions']
	if vd:
		model = list(zip(map(int, vd), [1]*len(vd)))
	else:
		model = [(1, 1), (1, 1), (2, 1)]

	ndiv = sum(x[0] or 1 for x in model)

	end = [
		executable/x
		for x in ('transcript',)
		if x not in excluding
	]
	# Exclude if there's only one division.
	end = end[:max(0, ndiv - 1)]

	nullcount = max(0, (ndiv - len(end)))
	rfq = itertools.chain(
		itertools.repeat(files.root@'/dev/null', nullcount),
		end,
	)

	return model, rfq

def configure_log_builtin(session, logfile=None):
	if logfile is not None:
		session.configure_logfile(open(logfile, 'a'))

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
	exepath = str(inv.parameters['system']['name'])
	if exepath[:1] != '/':
		for executable in query.executables(exepath):
			path = executable
			break
		else:
			# Unrecognized origin.
			path = files.root@'/var/empty/sy'
	else:
		path = files.root@exepath

	return path

def main(inv:process.Invocation) -> process.Exit:
	inv.imports(['TERMINAL_LOG', 'TERMINAL_SESSION'])
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

	remainder = recognition.merge(
		config, recognition.legacy(restricted, required, inv.argv),
	)

	path = identify_executable(inv)
	wd = configure_working_directory(config)

	configuration.load_sections()

	host = elements.Execution(
		types.System(
			'system',
			query.username(),
			'',
			query.hostname(),
		),
		'utf-8',
		str(next(query.executables('env'))),
		['env'],
	)
	host.export(os.environ.items())
	host.chdir(str(wd))

	device = types.Device()
	editor = elements.Session(
		configuration, host,
		IOManager.allocate(device.synchronize_io),
		path, device
	)
	configure_log_builtin(editor, inv.parameters['system']['environment'].get('TERMINAL_LOG'))

	fi = 0
	if remainder:
		session_file = (process.fs_pwd()@remainder[-1])
	else:
		session_file = (query.home()/'.syntax/Frames')
	editor.fs_snapshot = session_file

	try:
		editor.load()
	except Exception as restore_error:
		editor.error("Session restoration", restore_error)

	if not editor.frames:
		layout, rfq = configure_frame(wd, path, config)
		fi = editor.allocate(layout = layout)
		editor.frames[fi].fill(map(editor.refract, rfq))

	editor.reframe(fi)
	editor.log("Host: " + str(editor.host))
	editor.log("Factor: " + __name__)
	editor.log("Device: " + (config.get('interface-device') or "manager default"))
	editor.log("Environment:", *('\t'+k+'='+v for k,v in host.environment.items()))

	# System I/O loop for command substitution and file I/O.
	editor.io.service()

	try:
		while editor.frames:
			editor.cycle()
	finally:
		editor.store()
