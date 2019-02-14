"""
# Editor console.
"""
from fault.system import process
from fault.kernel import library as libkernel

from .. import library as libconsole

def main(inv:process.Invocation) -> process.Exit:
	spr = libkernel.system.Process.spawn(inv, libkernel.Unit, {'console':(libconsole.initialize,)}, 'root')
	spr.boot(())

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
