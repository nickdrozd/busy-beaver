#! /usr/bin/env python
#
# Macro_Machine_Filter.py
#
# This runs Busy Beaver Turing machines using macro steps and detects
# infinite left or right movement in one macro step.
#

from Turing_Machine import Turing_Machine, Turing_Machine_Runtime_Error, \
                           Filter_Unexpected_Return
from IO import IO

def Macro_Machine_Run(num_states, num_symbols, macro_size, tape_length,
                      max_steps, next, io):
  while next:
    machine_num = next[0]

    num_states  = next[1]
    num_symbols = next[2]

    old_tape_length = next[3]
    old_max_steps   = next[4]

    results = next[5]

    machine = Turing_Machine(num_states, num_symbols)
    machine.set_TTable(next[6])

    if (results[0] != 0 and results[0] != 4):
      Macro_Machine_Recursive(machine_num,
                              machine, num_states, num_symbols, macro_size,
                              tape_length, max_steps, results,
                              old_tape_length, old_max_steps, io)

    next = io.read_result()

def Macro_Machine_Recursive(machine_num,
                            machine, num_states, num_symbols, macro_size,
                            tape_length, max_steps,
                            old_results, old_tape_length, old_max_steps, io):
  results = run(machine.get_TTable(), num_states, num_symbols, macro_size,
                   tape_length, max_steps)

  exit_condition = results[0]

  #   -1) Error
  if exit_condition == -1:
    error_number = results[1]
    message      = results[2]
    sys.stderr.write("Error %d: %s\n" % (error_number, message))
    save_machine(machine_num, machine, results,
                 old_tape_length, old_ax_steps, io, old_results)
    raise Turing_Machine_Runtime_Error, "Error encountered while running a turing machine"

  # All other returns:
  #    0) Halt
  #    1) Exceed tape_length
  #    2) Exceed max_steps
  #    3) Reached Undefined Cell
  #    4) Are in a detected infinite loop
  else:
    # If classified (Halt, Undefined Cell, or Infinite)
    if (results[0] == 0 or results[0] == 3 or results[0] == 4):
      save_machine(machine_num, machine, results,
                   old_tape_length, old_max_steps, io, old_results)
    # If still unclassified
    else:
      save_machine(machine_num, machine, old_results,
                   old_tape_length, old_max_steps, io)

  return

def run(TTable, num_states, num_symbols, macro_size,
           tape_length, max_steps):
  """
  Wrapper for C machine running code.
  """
  import sys
  from Macro_Machine import Macro_Machine
  return Macro_Machine(TTable, num_states, num_symbols, macro_size,
                       tape_length, max_steps)

def save_machine(machine_num, machine, results, tape_length, max_steps, io,
                 old_results = []):
  """
  Saves a busy beaver machine with the provided data information.
  """
  io.write_result(machine_num, tape_length, max_steps, results, machine,
                  old_results = old_results)

# Default test code
if __name__ == "__main__":
  import sys
  from Option_Parser import Filter_Option_Parser

  # Get command line options.
  opts, args = Filter_Option_Parser(sys.argv, [("size", int, None, True, True)])

  io = IO(opts["infile"], opts["outfile"], opts["log_number"])
  next = io.read_result()

  Macro_Machine_Run(opts["states"], opts["symbols"], opts["size"],
                    opts["tape"], opts["steps"], next, io)
