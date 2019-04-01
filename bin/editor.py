"""
# Editor console.
"""
from fault.system import process
from fault.kernel import library as libkernel

from .. import library as libconsole

def main(inv:process.Invocation) -> process.Exit:
	exe = libconsole.Execution(inv, __name__)
	libkernel.system.spawn('root', [exe]).boot(exe.xact_initialize)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
