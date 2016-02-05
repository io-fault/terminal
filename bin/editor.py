"""
fault.io interactive console
"""
from .. import library as libconsole

name = 'console'
initialize = libconsole.initialize

if __name__ == '__main__':
	from ...io import library as libio
	libio.execute(console = (libconsole.initialize,))
