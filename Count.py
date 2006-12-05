#! /usr/bin/env python

def fact2(n, m=0):
  """Computes n!/m! = n*(n-1)*...*(m+1)"""
  assert n >= m >= 0
  if n == m:
    return 1
  else:
    return n*fact2(n-1, m)

def count(ttable):
  """Count the number of TM's that are equivolent to this one.
     With the restriction that A0->1RB and Halt=1RH."""
  undefs = 0
  has_halt = False
  max_symbol = 0
  max_state = 0
  num_states = len(ttable)
  num_symbols = len(ttable[0])
  # Get stats.  Number of undefined transitions, whether there is a halt and the max-symbol/states
  for state_in in range(num_states):
    for symbol_in in range(num_symbols):
      symbol, dir, state = ttable[state_in][symbol_in]
      if symbol == -1:
        undefs += 1
      elif state == -1:
        has_halt = True
      else:
        max_symbol = max(max_symbol, symbol)
        max_state = max(max_state, state)
  symbols_used = max_symbol + 1
  states_used = max_state + 1
  # Count the number of permutations of symbols/states possible
  result = fact2(num_symbols - 2, num_symbols - symbols_used) \
         * fact2(num_states - 2, num_states - states_used)
  if has_halt:
    result *= (2*num_states*num_symbols)**undefs
  else:
    result *= undefs * (2*num_states*num_symbols)**(undefs - 1)
  return result

#main prog
import sys, IO
total = 0
for filename in sys.argv[1:]:
  infile = open(filename, "r")
  io = IO.IO(infile, None)

  subtotal = 0
  next = io.read_result()
  while next:
    n = count(next[6])
    subtotal += n
    next = io.read_result()
  infile.close()
  print "", filename, subtotal
  sys.stdout.flush()
  total += subtotal
print "Total", total
