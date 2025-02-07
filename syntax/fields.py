"""
# Adapters for field isolation.
"""
from os.path import islink
from fault.context import tools
from fault.system import files
from fault.system.process import fs_pwd
from fault.syntax.format import Fields
from fault.syntax import keywords

def typed_path_fields(root, extension, *, separator='/'):
	"""
	# Format the path components in &extension relative to &root.
	"""

	current = root
	for f in extension[:-1]:
		if not f:
			yield ('path-empty', '')
		else:
			current = current/f

			if f in {'.', '..'}:
				yield ('relatives', f)
			else:
				if islink(current):
					yield ('path-link', f)
				else:
					try:
						typ = current.fs_type()
					except OSError:
						typ = 'warning'

					if typ == 'directory':
						yield ('path-directory', f)
					elif typ == 'void':
						yield ('file-not-found', f)
					else:
						yield (typ, f)

		yield ('path-separator', separator)

	f = extension[-1]
	final = current/f
	try:
		typ = final.fs_type()
	except OSError:
		typ = 'warning'

	# Slightly different from path segments.
	if typ == 'data':
		try:
			if final.fs_executable():
				typ = 'executable'
			elif f[:1] == '.':
				typ = 'dot-file'
			else:
				# No subtype override.
				pass
		except OSError:
			typ = 'warning'
	elif typ == 'void':
		typ = 'file-not-found'
	else:
		# No adjustments necessary.
		pass

	yield (typ, f)

def fs_isolate_path(pathref, ln, *, separator='/', relative=None):
	"""
	# Structure the path components of &line relative to &rpath.
	# If &line begins with a root directory, it is interpreted absolutely.
	"""

	s = separator
	lc = ln.ln_content
	if lc:
		if relative or not lc.startswith(s):
			return typed_path_fields(pathref(), lc.split(s), separator=s)
		else:
			return typed_path_fields(files.root, lc.split(s), separator=s)
	else:
		return ()

def kwf_qualify(tokens, context='inclusion'):
	"""
	# Convert a delimited KOS token stream into fields.
	"""

	for t in tokens:
		typ, qual, chars = t
		if typ == 'switch':
			context = qual
			continue

		if context == 'inclusion':
			if qual == 'event':
				yield ("-".join((context, typ)), chars)
			else:
				if typ == 'space':
					yield ("-".join((context, typ)), chars)
				else:
					yield ("-".join((context, qual, typ)), chars)
		else:
			if typ == 'space':
				yield ("-".join((context, 'space')), chars)
			elif qual == 'event' or typ == 'enclosure':
				yield ("-".join((context, 'words')), chars)
			else:
				yield ("-".join((context, qual)), chars)

def kwf_isolate(parser, ln):
	return kwf_qualify(parser.process_line(ln.ln_content))

def kwf_load(source):
	profile = keywords.Profile.from_keywords_v1(**source)
	parser = keywords.Parser.from_profile(profile)
	return Fields(parser, kwf_isolate)

filesystem_paths = Fields(fs_pwd, fs_isolate_path)
def prepare(method, config):
	if method == 'keywords':
		return kwf_load(config)
	else:
		raise LookupError("unknown field isolation interface")

def segmentation(ctlsize, tabsize=None):
	from fault.system.text import cells as syscellcount
	from ..cells.text import graphemes, words
	cus = tools.cachedcalls(256)(
		tools.compose(list, words,
			tools.partial(graphemes, syscellcount, ctlsize=ctlsize, tabsize=(tabsize or ctlsize))
		)
	)
