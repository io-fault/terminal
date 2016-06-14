"""
Editor console.
"""
from .. import library as libconsole
from ...io import library as libio

def main():
	libio.execute(console = (libconsole.initialize,))

if __name__ == '__main__':
	main()
