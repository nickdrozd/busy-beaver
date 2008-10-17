#! /usr/bin/env python
#
# Runlonger_Parallel_Once.py
#
# This is a Busy Beaver Turing machine program that runs in parallel (using
# pyMPI).  It enumerates a representative set of all Busy Beavers for given
# of states and symbols, runs the accelerated simulator, and records all
# results.
#
# This code runs each processor on a separate ".unknown.new" file that
# contains the current unknown TMs for that processor.  This TMs are then
# simulated for a longer time.  There is no load balancing except the
# balancing of the initial files.
#

import copy, sys, time, math, random, os, bz2
import cPickle as pickle
import mpi

from Turing_Machine import Turing_Machine
from IO import IO
import Macro_Simulator

def long_to_eng_str(number,left,right):
  if number != 0:
    expo = int(math.log(abs(number))/math.log(10))
    number_str = str(int(number / 10**(expo-right)))

    if number < 0:
      return "-%s.%se+%d" % (number_str[1     :1+left      ],
                             number_str[1+left:1+left+right],
                             expo)
    else:
      return "%s.%se+%d" % (number_str[0     :0+left      ],
                            number_str[0+left:0+left+right],
                            expo)
  else:
    return "0.%se+00" % ("0" * right)

class Stack(list):
  def __init__(self):
    self.me    = mpi.rank
    self.right = (self.me + 1) % mpi.procs
    self.left  = (self.me - 1) % mpi.procs
    self.ttime = 0.0
    self.send  = False
    
  def push(self, item):
    self.append(item)
    return self

class DefaultDict(dict):
  def __init__(self, default):
    self.default = default
  def __getitem__(self, item):
    return self.get(item, self.default)

class Runlonger(object):
  """Holds enumeration state information for checkpointing."""
  def __init__(self, num_states, num_symbols, max_steps, max_time, io, seed,
                     save_freq=100000, save_unk=False):
    self.num_states = num_states
    self.num_symbols = num_symbols
    self.max_steps = max_steps
    self.max_time = max_time
    self.io = io
    self.save_freq = save_freq
    self.save_unk = save_unk
    
    self.random = random
    self.random.seed(seed)
    self.stack = Stack()
    self.tm_num = 0
    
    self.num_halt = self.num_infinite = self.num_unresolved = 0
    self.best_steps = self.best_score = 0
    self.inf_type = DefaultDict(0)
    self.num_over_time = self.num_over_steps = 0
  
  def __getstate__(self):
    d = self.__dict__.copy()
    del d["io"], d["random"]
    d["random_state"] = self.random.getstate()
    return d
  
  def __setstate__(self, d):
    random.setstate(d["random_state"])
    del d["random_state"]
    self.__dict__ = d
    self.random = random
  
  def enum(self):
    """Enumerate all num_states*num_symbols TMs in Tree-Normal Form"""
    # blank_tm = Turing_Machine(self.num_states, self.num_symbols)
    # self.stack.push(blank_tm)
    self.continue_enum()

  def continue_enum(self):
    stime = time.time()
    i = 0
    self.start_time = time.time()
    while len(self.stack) > 0:
      if (i % self.save_freq) == 0:
        etime = time.time()
        self.save()
      i += 1
      # While we have machines to run, pop one off the stack ...
      cur_entry = self.stack.pop()
      if cur_entry == 0:
        etime = time.time()
        print "  stopped %d (%d) - %f..." % (mpi.rank,len(self.stack),etime-stime)
        sys.stdout.flush()
        return
      # ... and run it
      cur_TTable = cur_entry[6]
      cur_tm = Turing_Machine(cur_TTable)
      cond, info = self.run(cur_tm)
      
      # If it hits an undefined transition ...
      if cond == Macro_Simulator.UNDEFINED:
        on_state, on_symbol, steps, score = info
        # ... push all the possible non-halting transitions onto the stack ...
        self.add_transitions(cur_tm, on_state, on_symbol)
        # ... and make this tm the halting one (mutates cur_tm)
        self.add_halt_trans(cur_tm, on_state, on_symbol, steps, score)
      # Otherwise record defined result
      elif cond == Macro_Simulator.HALT:
        steps, score = info
        self.add_halt(cur_tm, steps, score)
        self.stack.extend([])
      elif cond == Macro_Simulator.INFINITE:
        reason, = info
        self.add_infinite(cur_tm, reason)
        self.stack.extend([])
      elif cond == Macro_Simulator.OVERSTEPS:
        steps, = info
        self.add_unresolved(cur_tm, cond, steps)
        self.stack.extend([])
      elif cond == Macro_Simulator.TIMEOUT:
        runtime, steps = info
        self.add_unresolved(cur_tm, cond, steps, runtime)
        self.stack.extend([])
      else:
        raise Exception, "Runlonger.enum() - unexpected condition (%r)" % cond

    etime = time.time()
    print "  done %d (%d) - %f..." % (mpi.rank,len(self.stack),etime-stime)
    sys.stdout.flush()

    self.save()
  
  def save(self):
    self.end_time = time.time()

    print self.num_halt+self.num_infinite+self.num_unresolved,        \
          mpi.rank, "(%d) -" % len(self.stack),                       \
          self.num_halt, self.num_infinite, self.num_unresolved, "-", \
          long_to_eng_str(self.best_steps,1,3),                       \
          long_to_eng_str(self.best_score,1,3),                       \
          "(%.2f)" % (self.end_time - self.start_time)
    sys.stdout.flush()

    self.start_time = time.time()

    # checkpoint = file(self.checkpoint_filename, "wb")
    # pickle.dump(self, checkpoint)
    # checkpoint.close()
  
  def run(self, tm):
    return Macro_Simulator.run(tm.get_TTable(), self.max_steps, self.max_time)
  
  def add_transitions(self, old_tm, state_in, symbol_in):
    """Push Turing Machines with each possible transition at this state and symbol"""
    # 'max_state' and 'max_symbol' are the state and symbol numbers for the
    # smallest state/symbol not yet written (i.e. available to add to TTable).
    max_state  = old_tm.get_num_states_available()
    max_symbol = old_tm.get_num_symbols_available()
    # If this is the last undefined cell, then it must be a halt, so only try
    # other values for cell if this is not the last undefined cell.
    if old_tm.num_empty_cells > 1:
      # 'state_out' in [0, 1, ... max_state] == xrange(max_state + 1)
      new_tms = []
      for state_out in xrange(max_state + 1):
        for symbol_out in xrange(max_symbol + 1):
          for direction_out in xrange(2):
            new_tm = copy.deepcopy(old_tm)
            new_tm.add_cell(state_in , symbol_in ,
                            state_out, symbol_out, direction_out)
            new_tms.append(new_tm)

      self.random.shuffle(new_tms)

      # Stack format is silly - match new_tms to silly format
      for i in xrange(len(new_tms)):
        new_tms[i] = (None, None, None, None, None, None, new_tms[i].get_TTable(), None, [])

      # Push the (randomize) list of TMs onto the stack
      self.stack.extend(new_tms)
    else:
      self.stack.extend([])

  def add_halt_trans(self, tm, on_state, on_symbol, steps, score):
    #   1) Add the halt state
    tm.add_cell(on_state, on_symbol, -1, 1, 1)
    #   2) Save this machine
    self.add_halt(tm, steps, score)
  
  def add_halt(self, tm, steps, score):
    self.num_halt += 1
    self.io.write_result(self.tm_num, -1, -1, (0, score, steps), tm)
    if steps > self.best_steps or score > self.best_score:
      ## Magic nums: the '-1' is for tape size (not used) .. the '0' is for halting.
      self.best_steps = max(self.best_steps, steps)
      self.best_score = max(self.best_score, score)
    self.tm_num += 1

  def add_infinite(self, tm, reason):
    self.io.write_result(self.tm_num, -1, -1, (4, "Infinite"), tm)
    self.num_infinite += 1
    self.inf_type[reason] += 1
    self.tm_num += 1

  def add_unresolved(self, tm, cond, steps, runtime=None):
    self.io.write_result(self.tm_num, -1, -1, (2, "Timeout"), tm)
    self.num_unresolved += 1
    if runtime == None:
      self.num_over_steps
    else:
      self.num_over_time
    self.tm_num += 1

# Command line interpretter code
if __name__ == "__main__":
  nprocs = mpi.procs
  rank   = mpi.rank

  if rank == 0:
    from Option_Parser_Parallel import Filter_Option_Parser
    
    # Get command line options.
    opts, args = Filter_Option_Parser(sys.argv, 
            [("time",      float,                     15, False, True), 
             ("save_freq",   int,                 100000, False, True),
             ("seed",       long, long(1000*time.time()), False, True),
             ("save_unk"  , None,                  False, False, False)])

    steps = (opts["steps"] if opts["steps"] > 0 else Macro_Simulator.INF)
    io = IO(None, opts["outfile"], opts["log_number"])

    save_unk_str = ""
    if opts["save_unk"]:
      save_unk_str = " --save_unk"

    print "Runlonger_Parallel_Once.py --infile=%s --steps=%s --time=%s --save_freq=%s --seed=%s --outfile=%s%s --states=%s --symbols=%s" % \
          (opts["infilename"],opts["steps"],opts["time"],opts["save_freq"],opts["seed"],opts["outfilename"],save_unk_str,opts["states"],opts["symbols"])
    sys.stdout.flush()

    if opts["log_number"] != None:
      print "--log_number=%s" % (opts["log_number"])
    else:
      print ""

    states      = opts["states"]
    symbols     = opts["symbols"]
    timeout     = opts["time"]
    outfilename = opts["outfilename"]
    log_number  = opts["log_number"]
    seed        = opts["seed"]
    save_freq   = opts["save_freq"]
    save_unk    = opts["save_unk"]

    mpi.bcast((states,symbols,steps,timeout,outfilename,log_number,seed,save_freq,save_unk))

    infile = opts["infile"]

    if outfilename == "-":
      outfile = sys.stdout
    else:
      outfilename = outfilename + ".%05d" % rank
      if os.path.exists(outfilename):
        sys.stderr.write("Output test file, '%s', exists\n" % outfilename)
        sys.exit(1)
      # outfile = bz2.BZ2File(outfilename, "w")
      outfile = file(outfilename, "w")

    # io = IO(None, outfile, log_number, True)
    io = IO(infile, outfile, log_number, False)

    all = []

    count = 0
    next = io.read_result()
    if next:
      all.append(next)

    while next:
      count += 1
      next = io.read_result()
      if next:
        all.append(next)

    print "Worker: " + str(rank) + " (" + str(nprocs) + ") - " + str(count) + "..."
    sys.stdout.flush()

    runmore = Runlonger(states, symbols, steps, 
                      timeout, io, seed, save_freq, save_unk)

    init_stack = mpi.scatter(all)

    runmore.stack = init_stack[:]

    print "Worker: " + str(rank) + " (" + str(nprocs) + ") - " + str(len(init_stack)) + " (" + str(len(runmore.stack)) + ")..."
    sys.stdout.flush()
    
    runmore.enum()
  else:
    params = mpi.bcast()

    states      = params[0]
    symbols     = params[1]
    steps       = params[2]
    timeout     = params[3]
    outfilename = params[4]
    log_number  = params[5]
    seed        = params[6]
    save_freq   = params[7]
    save_unk    = params[8]

    if outfilename == "-":
      outfile = sys.stdout
    else:
      outfilename = outfilename + ".%05d" % rank
      if os.path.exists(outfilename):
        sys.stderr.write("Output test file, '%s', exists\n" % outfilename)
        sys.exit(1)
      # outfile = bz2.BZ2File(outfilename, "w")
      outfile = file(outfilename, "w")

    print "Worker: " + str(rank) + " (" + str(nprocs) + ")..."
    sys.stdout.flush()

    io = IO(None, outfile, log_number, False)

    runmore = Runlonger(states, symbols, steps, 
                      timeout, io, seed, save_freq, save_unk)

    all = []
    init_stack = mpi.scatter(all)

    runmore.stack = init_stack[:]

    print "Worker: " + str(rank) + " (" + str(nprocs) + ") - " + str(len(init_stack)) + " (" + str(len(runmore.stack)) + ")..."
    sys.stdout.flush()

    runmore.enum()

  print "Worker: " + str(rank) + " (" + str(nprocs) + ") - done..."
  sys.stdout.flush()

  outfile.close()