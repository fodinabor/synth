#! /usr/bin/env python3
import math

from dataclasses import dataclass

from z3 import *

from synth.spec import Func, Spec
from synth.oplib import Bv

from bench.util import BitVecBenchSet

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import Loader

from collections import defaultdict
import multiprocessing as mp

def load_yaml(path):
    with open(path, 'r') as f:
        yml = yaml.load_all(f, Loader=Loader)
        print(next(yml), file=sys.stderr)
        patterns = []
        for doc in yml:
            patterns.append(doc)
        print(f"loaded {path}", file=sys.stderr)
    return patterns

def load_patterns(path):
    files = []
    for file in os.scandir(path): # do we have any relevant json file here?
        if os.path.isfile(file.path) and file.path.endswith(".yml"):
            files.append(file.path)

    with mp.Pool() as pool:
        workers = len(mp.active_children())
        patterns_lists = pool.imap(load_yaml, files, (len(files) + workers - 1) // workers)
        patterns = []
        for pttrns in patterns_lists:
            patterns.extend(pttrns)
    return patterns


@dataclass
class ComPileBench(BitVecBenchSet):
    pattern_dir: str = "patterns"

    def __init__(self, pattern_dir="patterns", bit_width: int = 8):
        super().__init__(bit_width)
        self.pattern_dir = pattern_dir
        patterns = load_patterns(self.pattern_dir)
        self.bv    = Bv(bit_width)
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
            return If(ULE(args[0], args[1]), self.one, self.zero)
        elif opcode == "icmpuge":
            return If(UGE(args[0], args[1]), self.one, self.zero)
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
        return self.create_bench('p'+str(x), spec, self.ops, consts, desc='Pattern!')

