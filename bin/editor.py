"""
# Editor console.
"""
from fault.system import process
from fault.io import library as libio

from .. import library as libconsole

def main(inv:process.Invocation) -> process.Exit:
	spr = libio.system.Process.spawn(inv, libio.Unit, {'console':(libconsole.initialize,)}, 'root')
	spr.boot(())

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
