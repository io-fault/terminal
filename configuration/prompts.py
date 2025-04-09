"""
# Prompt dimensions and behaviors.

# [ Elements ]
# /syntax_type/
	# The default syntax type of the prompt itself.
# /line_allocation/
	# The number of display lines to allocate when displaying the
	# prompt of a division. Default and minimum is `1`. Upper bounds
	# is dependent on the division's content height.
# /execution_types/
	# The syntax types that will be configured to automatically display
	# the prompt and focus the prompt when switched to.
"""

syntax_type = 'prompt'
line_allocation = 1
execution_types = {
	'transcript',
}
