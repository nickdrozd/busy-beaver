"""
Shared constants and constructs.
"""

class Exit_Condition(object):
  """Basically an enum of Turing machine exit conditions."""
  # TODO(shawn): It'd be nice to convert these to strings or something less
  # cryptic. However, these constants have weasled there way throughout the
  # code. For example, they are in Turing_Machine_Sim.c, Macro_Machine.c and
  # Dual_Machine.c :/
  ERROR = -1
  HALT = 0
  UNDEF_CELL = 3
  INFINITE = 4

  # Generic unknown condition, we should move to this and add extra info as
  # reason text (Result.category_results).
  UNKNOWN = 2  # Make it redundant with MAX_STEPS for backwards compatibility.
  OVER_TAPE = 1
  MAX_STEPS = 2
  TIME_OUT = 5
  # Set of all unkown conditions
  UNKNOWN_SET = (UNKNOWN, OVER_TAPE, MAX_STEPS, TIME_OUT)

  names = { ERROR: "Error",
            HALT: "Halt",
            UNDEF_CELL: "Undefined_Cell",
            INFINITE: "Infinite",
            # TODO(shawn): Print out "Unknown" for all of these.
            OVER_TAPE: "Over_Tape",
            MAX_STEPS: "Max_Steps",
            TIME_OUT: "Time_Out",
            }
  condition_from_name = dict((name, cond) for (cond, name) in names.items())

  @classmethod
  def name(cls, cond):
    """Convert Exit_Conditions to strings."""
    return cls.names[cond]

  @classmethod
  def read(cls, name):
    """Read Exit_Condition strings into constants."""
    return cls.condition_from_name[name]

HALT_TRANS = (1, 1, -1)
HALT_STATE = -1