#! /usr/bin/env python

import sys

from Macro import Turing_Machine, Chain_Simulator, Block_Finder
import IO

def run(TTable, block_size, back, prover, rec, verbose, options):
  # Construct Machine (Backsymbol-k-Block-Macro-Machine)
  m = Turing_Machine.make_machine(TTable)
  # If no explicit block-size given, use inteligent software to find one
  if not block_size:
    Block_Finder.DEBUG = True
    block_size = Block_Finder.block_finder(m, options.bf_limit1, options.bf_limit2, options.bf_run1, options.bf_run2, options.bf_extra_mult)
  # Do not create a 1-Block Macro-Machine (just use base machine)
  if block_size != 1:
    m = Turing_Machine.Block_Macro_Machine(m, block_size)
  if back:
    m = Turing_Machine.Backsymbol_Macro_Machine(m)

  global sim
  sim = Chain_Simulator.Simulator()
  sim.init(m, rec)
  if not prover:
    sim.proof = None
  extent = 1
  #raw_input("Ready?")
  try:
    while sim.op_state == Turing_Machine.RUNNING:
      if verbose: sim.print_self()
      sim.seek(extent)
      extent *= 10
  finally:
    sim.print_self()

  if sim.op_state == Turing_Machine.HALT:
    print
    print "Turing Machine Halted!"
    print "Steps:   ", sim.step_num
    print "Nonzeros:", sim.get_nonzeros()
  elif sim.op_state == Turing_Machine.INF_REPEAT:
    print
    print "Turing Machine proven Infinite!"
    print "Reason:", sim.inf_reason
  elif sim.op_state == Turing_Machine.UNDEFINED:
    print
    print "Turing Machine reached Undefined transition!"
    print "State: ", sim.op_details[0][1]
    print "Symbol:", sim.op_details[0][0]
    print "Steps:   ", sim.step_num
    print "Nonzeros:", sim.get_nonzeros()


if __name__ == "__main__":
  from optparse import OptionParser, OptionGroup
  # Parse command line options.
  usage = "usage: %prog [options] machine_file [line_number]"
  parser = OptionParser(usage=usage)
  #parser.set_defaults(verbose=True)
  parser.add_option("-q", "--quiet", action="store_true", help="Brief output")
  parser.add_option("--verbose-prover", action="store_true", help="Provide debuggin output from prover")
  parser.add_option("--verbose-simulator", action="store_true", help="Provide debuggin output from simulator")
  parser.add_option("--verbose-block-finder", action="store_true", help="Provide debuggin output from block_finder")
  
  parser.add_option("-b", "--no-backsymbol", action="store_false", dest="backsymbol", default=True, 
                    help="Turn off backsymbol macro machine")
  parser.add_option("-p", "--no-prover", action="store_false", dest="prover", default=True, 
                    help="Turn off proof system")
  parser.add_option("-r", "--recursive", action="store_true", default=False, 
                    help="Turn ON recursive proof system [Very Experimental]")
  
  parser.add_option("-n", "--block-size", type=int, help="Block size to use in macro machine simulator (default is to guess with the block_finder algorithm)")
  
  block_options = OptionGroup(parser, "Block Finder options")
  block_options.add_option("--bf-limit1", type=int, default=1000, metavar="LIMIT", help="Number of steps to run the first half of block finder [Default: %default].")
  block_options.add_option("--bf-limit2", type=int, default=1000, metavar="LIMIT", help="Number of stpes to run the second half of block finder [Default: %default].")
  block_options.add_option("--bf-run1", action="store_true", default=True, help="In first half, find worst tape before limit.")
  block_options.add_option("--bf-no-run1", action="store_false", dest="bf_run1", help="In first half, just run to limit.")
  block_options.add_option("--bf-run2", action="store_true", default=True, help="Run second half of block finder.")
  block_options.add_option("--bf-no-run2", action="store_false", dest="bf_run2", help="Don't run second half of block finder.")
  block_options.add_option("--bf-extra-mult", type=int, default=2, metavar="MULT", help="How far ahead to search in second half of block finder.")
  parser.add_option_group(block_options)
  
  (options, args) = parser.parse_args()
  
  # Verbose Prover
  if options.verbose_prover:
    Chain_Simulator.Chain_Proof_System.DEBUG = True
  else:
    Chain_Simulator.Chain_Proof_System.DEBUG = False
  
  # Verbose Simulator
  if options.verbose_simulator:
    Chain_Simulator.DEBUG = True
    verbose = False
  else:
    Chain_Simulator.DEBUG = False
    verbose = True
  
  # Verbose Block Finder
  if options.verbose_block_finder:
    Block_Finder.DEBUG = True
  else:
    Block_Finder.DEBUG = False
  
  # Brief Simulator output
  if options.quiet:
    Chain_Simulator.DEBUG = False
    verbose = False
  
  if len(args) < 1:
    parser.error("Must have at least one argument, machine_file")
  filename = args[0]
  
  if len(args) >= 2:
    try:
      line = int(args[1])
    except ValueError:
      parser.error("line_number must be an integer.")
    if line < 1:
      parser.error("line_number must be >= 1")
  else:
    line = 1
  
  ttable = IO.load_TTable_filename(filename, line)
  
  run(ttable, options.block_size, options.backsymbol, options.prover, 
              options.recursive, verbose, options)
