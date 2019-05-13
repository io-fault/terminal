"""
# Editor console.
"""
from fault.system import process
from .. import library as libconsole

def main(inv:process.Invocation) -> process.Exit:
	from fault.kernel import system
	system.dispatch(inv, libconsole.Editor())
	system.control()

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
