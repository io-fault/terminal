from .. import fields
from . import types
from . import navigation
event, Index = types.Index.allocate('console')

@event('prepare', 'open')
def event_prepare_open(self, event):
	prompt = getattr(self, 'prompt', None) or self.sector.prompt

	fs = fields.String("")
	prompt.prepare(fields.String("open"), fs)

	navigation.span_line(prompt, None)
	prompt.horizontal.move(0, -1)
	prompt.keyboard.set('edit')
	try:
		self.focus_prompt()
	except AttributeError:
		self.sector.focus_prompt()

@event('prepare', 'search')
def event_console_search(self, event):
	console = self.sector
	prompt = console.prompt
	prompt.prepare(fields.String("search"), fields.String(""))
	prompt.horizontal.configure(8, 8, 0)
	prompt.transition_keyboard('edit')
	console.focus_prompt()
	self.update_horizontal_indicators()

@event('prepare', 'write')
def event_console_save(self, event):
	console = self.sector
	console.prompt.prepare(fields.String("write"), fields.String(self.source))
	console.focus_prompt()

@event('prepare', 'seek')
def event_console_seek_line(self, event):
	console = self.sector
	prompt = console.prompt
	prompt.prepare(fields.String("seek"), fields.String(""))
	navigation.span_line(prompt, None)
	prompt.horizontal.move(0, -1)
	prompt.keyboard.set('edit')
	console.focus_prompt()

@event('print', 'unit')
def print_representation(self, event):
	"""
	# Display the structure of the current unit to the transcript.
	"""
	hf = self.horizontal_focus
	l = [hf[1].__class__.__name__ + ': ' + str(len(hf[1]))]
	l.extend(
		x.__class__.__name__ + ': ' + repr(x) + ' [' + str(path[1:]) + ']'
		for (path, x) in hf.subfields()
	)
	l.append('')
	self.transcript_write('\n'.join(l))
	import pprint
	s = pprint.pformat(self.phrase(hf))
	self.transcript_write(s+'\n')
