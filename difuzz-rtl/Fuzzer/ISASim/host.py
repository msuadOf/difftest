import sys
import os
import subprocess

class isaInput():
    def __init__(self, binary, intrfile):
        self.binary = binary
        self.intrfile = intrfile

class rvISAhost():
    def __init__(self, spike, spike_args, isa_sigfile, debug=False):
        self.spike = spike
        self.spike_args = spike_args
        self.isa_sigfile = isa_sigfile

        self.debug= debug

    def debug_print(self, message):
        if self.debug:
            print(message)

    def run_test(self, isa_input: isaInput, assert_intr=False, trace_file=None):
        binary = isa_input.binary
        if assert_intr: intr = [ '--intr={}'.format(isa_input.intrfile) ]
        else: intr = []

        args = [ self.spike ] + self.spike_args + intr + \
            [ '+signature={}'.format(self.isa_sigfile), binary ]

        # 如果指定了 trace_file，加 -l 开启 itrace 并重定向到文件
        if trace_file:
            args = [self.spike, '-l'] + self.spike_args + intr + \
                [ '+signature={}'.format(self.isa_sigfile), binary ]

        self.debug_print('[ISAHost] Start ISA simulation')

        if trace_file:
            with open(trace_file, 'w') as tf:
                return subprocess.call(args, stderr=tf)
        else:
            return subprocess.call(args)
