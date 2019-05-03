"""
# Editor console.
"""
from fault.system import process
from fault.kernel import system

from .. import library as libconsole

def main(inv:process.Invocation) -> process.Exit:
	exe = libconsole.Execution(inv, __name__)
	system.spawn('root', [exe]).boot(exe.xact_initialize)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
