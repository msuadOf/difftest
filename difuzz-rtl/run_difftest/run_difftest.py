import os
import sys

from cocotb.regression import TestFactory

# Add necessary paths like Fuzzer/src, just in case Makefile didn't cover Python level imports perfectly everywhere
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Fuzzer'))

from src.env_parser import envParser
from runner import RunDifftest

parser = envParser()

parser.add_option('toplevel', None, 'Toplevel module of DUT')
parser.add_option('template', '../Fuzzer/Template', 'Template test file location')
parser.add_option('elf_file', '', 'Raw .elf file to convert and execute with symbol checking.')
parser.add_option('out', 'output', 'Directory to save the result')
parser.add_option('debug', 0, 'Debugging?')

parser.print_help()
parser.parse_option()

out = parser.arg_map['out'][0]
toplevel = parser.arg_map['toplevel'][0]
template = parser.arg_map['template'][0]
elf_file = parser.arg_map['elf_file'][0]
debug = parser.arg_map['debug'][0]

if not os.path.isdir(out):
    os.makedirs(out)

factory = TestFactory(RunDifftest)

# Registering arguments to be passed as kwargs to the coroutine RunDifftest
factory.add_option('toplevel', [toplevel])
factory.add_option('template', [template])
factory.add_option('elf_file', [elf_file])
factory.add_option('out', [out])
factory.add_option('debug', [debug])

factory.generate_tests()
