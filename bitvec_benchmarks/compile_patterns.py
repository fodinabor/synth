#! /usr/bin/env python3

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math

from z3 import *
from cegis import *
from oplib import Bv
from test_base import TestBase, parse_standard_args

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import Loader
from collections import defaultdict
import multiprocessing as mp

def chunks(lst, n):
  """Yield successive n-sized chunks from lst."""
  for i in range(0, len(lst), n):
      yield lst[i:i + n]

class BvBench(TestBase):
    def __init__(self, width, patterns, args):
        super().__init__(**vars(args))
        self.width = width
        self.bv    = Bv(width)
        self.ops = [
            self.bv.add_,
            self.bv.sub_,
            self.bv.and_,
            self.bv.or_,
            self.bv.xor_,
            self.bv.neg_,
            self.bv.not_,
            self.bv.ashr_,
            self.bv.lshr_,
            self.bv.shl_,
            self.bv.eq_,
            self.bv.ult_,
            self.bv.uge_,
            self.bv.slt_,
            self.bv.sge_,
        ]
        self.one = BitVecVal(1, self.width)
        self.zero = BitVecVal(0, self.width)

        self.patterns = patterns

        num_zeros = int(math.ceil(math.log10(len(self.patterns))))
        for i in range(len(self.patterns)):
            setattr(self, f"test_p{str(i).zfill(num_zeros)}", lambda i=i: self.synth_px(i))

    def get_op(self, opcode, *args):
        if opcode == "add":
            return args[0] + args[1]
        elif opcode == "sub":
            return args[0] - args[1]
        elif opcode == "mul":
            return args[0] * args[1]
        elif opcode == "div":
            return args[0] / args[1]
        elif opcode == "rem":
            return args[0] % args[1]
        elif opcode == "shl":
            return args[0] << args[1]
        elif opcode == "lshr":
            return LShR(args[0], args[1])
        elif opcode == "ashr":
            return args[0] >> args[1]
        elif opcode == "and":
            return args[0] & args[1]
        elif opcode == "or":
            return args[0] | args[1]
        elif opcode == "xor":
            return args[0] ^ args[1]
        elif opcode == "neg":
            return -args[0]
        elif opcode == "not":
            return ~args[0]
        elif opcode == "icmpeq":
            return If(args[0] == args[1], self.one, self.zero)
        elif opcode == "icmpult":
            return If(ULT(args[0], args[1]), self.one, self.zero)
        elif opcode == "icmpugt":
            return If(UGT(args[0], args[1]), self.one, self.zero)
        elif opcode == "icmpule":
            return If(ULE(args[0] <= args[1]), self.one, self.zero)
        elif opcode == "icmpuge":
            return If(UGE(args[0] >= args[1]), self.one, self.zero)
        elif opcode == "icmpslt":
            return If(args[0] < args[1], self.one, self.zero)
        elif opcode == "icmpsgt":
            return If(args[0] > args[1], self.one, self.zero)
        elif opcode == "icmpsle":
            return If(args[0] <= args[1], self.one, self.zero)
        elif opcode == "icmpsge":
            return If(args[0] >= args[1], self.one, self.zero)
        elif opcode == "icmpne":
            return If(args[0] != args[1], self.one, self.zero)
        else:
            raise ValueError(f"unknown opcode {opcode}")
        
    def do_synth(self, name, spec, ops, consts={}, desc='', **args):
        return super().do_synth(name, spec, ops, self.ops, consts, desc, \
                                theory='QF_BV', **args)

    def const(self, n):
        return BitVecVal(n, self.width)

    def popcount(self, x):
        res = BitVecVal(0, self.width)
        for i in range(self.width):
            res = ZeroExt(self.width - 1, Extract(i, i, x)) + res
        return res

    def nlz(self, x):
        w   = self.width
        res = BitVecVal(w, w)
        for i in range(w - 1):
            res = If(And([ Extract(i, i, x) == 1,
                     Extract(w - 1, i + 1, x) == BitVecVal(0, w - 1 - i) ]), w - 1 - i, res)
        return If(Extract(w - 1, w - 1, x) == 1, 0, res)

    def is_power_of_two(self, x):
        return self.popcount(x) == 1

    def synth_px(self, x):
        pattern = self.patterns[x]
        insts = []
        op_id = 0
        for inst in pattern['Insts']:
            opcode = inst['OpCodeName']
            ops = []
            for op in inst['Ops']:
                if op['Kind'] == 'A':
                    ops.append(BitVec('op'+str(op_id), self.width))
                    op_id += 1
                elif op['Kind'] == 'I':
                    ops.append(insts[op['Id']])
            insts.append(self.get_op(opcode, *ops))

        print(insts[-1])
        spec = Func('p'+str(x), insts[-1])
        print(spec)
        # ops = { self.bv.and_: 1, self.bv.sub_: 1, self.bv.xor_: 1, self.bv.add_: 1, self.bv.ult_: 1, self.bv.uge_: 1, self.bv.shl : 1, self.bv.lshr_: 1 }
        consts = { self.one: 1, self.zero: 1 }
        return self.do_synth('p'+str(x), spec, self.ops, consts, desc='Pattern!')


if __name__ == '__main__':
    import argparse
    synth_args, rest = parse_standard_args()
    parser = argparse.ArgumentParser(prog="hackdel")
    parser.add_argument('-b', '--width', type=int, default=8)
    parser.add_argument("patterns", type=str, default="patterns", help="path to the patterns")
    args = parser.parse_args(rest)

    path = args.patterns
    files = []
    for file in os.scandir(path): # do we have any relevant json file here?
        if os.path.isfile(file.path) and file.path.endswith(".yml"):
            files.append(file.path)
    
    def load_yaml(path):
        with open(path, 'r') as f:
            yml = yaml.load_all(f, Loader = Loader)
            print(next(yml), file=sys.stderr)
            patterns = []
            for doc in yml:
                patterns.append(doc)
            print(f"loaded {path}", file=sys.stderr)
        return patterns
    with mp.Pool() as pool:
        workers = len(mp.active_children())
        patterns_lists = pool.imap(load_yaml, files, (len(files) + workers - 1) // workers)
        patterns = []
        for pttrns in patterns_lists:
            patterns.extend(pttrns)

    t = BvBench(args.width, patterns, synth_args)
    t.run()
