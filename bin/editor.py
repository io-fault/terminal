"""
# Editor console.
"""
from .. import library as libconsole
from fault.io import library as libio

def main():
	libio.execute(console = (libconsole.initialize,))

if __name__ == '__main__':
	main()
