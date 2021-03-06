from __future__ import division

import copy
import sys

import Chain_Simulator
import Turing_Machine

DEBUG = False

def block_finder(machine, limit=200):
  """Tries to find the optimal block-size for macromachines"""
  ## First find the minimum efficient tape compression size
  sim = Chain_Simulator.Simulator()
  sim.init(machine)
  sim.proof = None # Level 2 machine

  # The original method was very time consuming and was originally not
  #   implemented correctly. Now we just run for limit steps.
  sim.run(limit)

  '''
  # Run sim to find when the tape is least compressed with macro size 1
  max_length = len(sim.tape.tape[0]) + len(sim.tape.tape[1])
  worst_time = 0
  worst_tape = copy.deepcopy(sim.tape.tape)
  for i in range(limit):
    sim.step()
    l = len(sim.tape.tape[0]) + len(sim.tape.tape[1])
    if l > max_length:
      max_length = l
      worst_time = sim.step_num
      worst_tape = copy.deepcopy(sim.tape.tape)
    # If it has stopped running then this is a good block size!
    if sim.op_state != Turing_Machine.RUNNING:
      if DEBUG:
        print "Halted, returning base block size: 1"
      return 1
  if DEBUG:
    print "Least compression at time:", worst_time
    #print worst_tape
    sys.stdout.flush()
  '''

  # Analyze this time to see which block size provides greatest compression
  tape = uncompress_tape(sim.tape.tape)
  min_compr = len(tape) + 1 # Worse than no compression
  opt_size = 1
  for block_size in range(1, len(tape)//2):
    compr_size = compression_efficiency(tape, block_size)
    if compr_size < min_compr:
      min_compr = compr_size
      opt_size = block_size
  if DEBUG:
    print "Optimal base block size:", opt_size
    sys.stdout.flush()
  return opt_size

  ## Then try a couple different multiples of this base size to find best speed
  max_chain_factor = 0
  opt_mult = 1
  mult = 1
  while mult <= opt_mult + 2:
    block_machine = Turing_Machine.Block_Macro_Machine(machine, mult*opt_size)
    back_machine = Turing_Machine.Backsymbol_Macro_Machine(block_machine)
    sim.init(back_machine)
    sim.proof = None # Level 2 machine
    sim.loop_seek(limit)
    if sim.op_state != Turing_Machine.RUNNING:
      return mult*opt_size
    chain_factor = sim.steps_from_chain / sim.steps_from_macro
    #print mult, chain_factor
    # Note that we preffer smaller multiples
    # We only choose larger multiples if they perform much better
    if chain_factor > 2*max_chain_factor:
      max_chain_factor = chain_factor
      opt_mult = mult
    mult += 1
  if DEBUG:
    print "Optimal block mult:", opt_mult
    sys.stdout.flush()
  return opt_mult*opt_size

def uncompress_tape(compr_tape):
  """Expand out repatition counts in tape."""
  tape_out = []
  left_tape = compr_tape[0][1:]
  right_tape = compr_tape[1][1:]
  right_tape.reverse()
  for seq in left_tape + right_tape:
    tape_out += [seq.symbol]*seq.num
  return tape_out

def compression_efficiency(tape, k):
  """Find size of tape when compressed with blocks of size k."""
  compr_size = len(tape)
  for i in range(0, len(tape) - 2*k, k):
    if tape[i:i + k] == tape[i + k:i + 2*k]:
      compr_size -= k
  return compr_size

