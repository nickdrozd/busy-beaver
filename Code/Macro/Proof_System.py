#
# Proof_System.py
#
"""
Proof System which observes and attempts to prove patterns in computation.
"""

import copy
from collections import defaultdict
import operator
import optparse
from optparse import OptionParser, OptionGroup
import sys

import Simulator
import Tape
import Turing_Machine

parent_dir = sys.path[0][:sys.path[0].rfind("/")] # pwd path with last directory removed
sys.path.insert(1, parent_dir)
from Numbers.Algebraic_Expression import Algebraic_Expression, Variable, NewVariableExpression, VariableToExpression, ConstantToExpression, is_scalar, BadOperation


def add_option_group(parser):
  """Add Proof_System options group to an OptParser parser object."""
  assert isinstance(parser, OptionParser)

  group = OptionGroup(parser, "Proof System options")

  group.add_option("--verbose-prover", action="store_true")
  group.add_option("-r", "--recursive", action="store_true", default=False,
                   help="Turn ON recursive proof system.")
  group.add_option("--allow-collatz", action="store_true", default=False,
                   help="Allow Collatz-style recursive proofs. [Experimental]")
  group.add_option("--limited-rules", action="store_true", default=False,
                   help="Rules are saved and applied based on the maximum they "
                   "effect the tape to the left and right. [Experimental]")
  group.add_option("--max-num-reps", type=int, default=10,
                    help="Specify a maximum consecutive number of times a rule is applied.")

  parser.add_option_group(group)


UNPROVEN_PARITY = "Unproven parity"

class Rule(object):
  """Base type for Proof_System rules."""

class Diff_Rule(Rule):
  """A rule that specifies constant deltas for each tape block's exponent."""
  def __init__(self, initial_tape, diff_tape, initial_state, num_steps, num_loops, rule_num):
    # TODO: Use basic lists instead of tapes, we never use the symbols.
    # TODO: Have a variable list and a min list instead of packing both
    # into init_tape.
    # TOOD: Or maybe we don't even need variables, we could just have the
    # things that depend on variables index directly into the tapes?
    # TODO: Actually, variables only appear in num_steps, so we don't even
    # need them if we are not computing steps.
    self.initial_tape = initial_tape
    self.diff_tape = diff_tape
    self.num_steps = num_steps
    self.initial_state = initial_state
    self.num_loops = num_loops
    self.name = str(rule_num)  # Unique identifier.
    self.num_uses = 0  # Number of times this rule has been applied.

  def __repr__(self):
    return ("Diff Rule %s\nInitial Config: %s\nDiff Config:    %s\nSteps: %s, Loops: %s"
            % (self.name, self.initial_tape.print_with_state(self.initial_state), self.diff_tape.print_with_state(self.initial_state), self.num_steps,
               self.num_loops))

class General_Rule(Rule):
  """A general rule that specifies any general end configuration."""
  def __init__(self, var_list, min_list,
               result_tape, num_steps, num_loops, rule_num):
    assert len(var_list) == len(min_list)
    self.var_list = var_list  # List of variables (or None) to assign repetition counts to.
    self.min_list = min_list  # List of minimum values for variables.
    # TODO: result_list and force output tape to be the same stripped config as input tape.
    self.result_tape = result_tape
    self.result_list = [block.num for block in result_tape.tape[0] + result_tape.tape[1]]
    self.num_steps = num_steps
    self.num_loops = num_loops
    self.name = str(rule_num)
    self.num_uses = 0

    # Is this an infinite rule?
    self.infinite = True
    for var, result in zip(self.var_list, self.result_list):
      if var:  # If this exponent changes in this rule (has a variable)
        if is_scalar(result) or not result.always_greater_than(VariableToExpression(var)):
          # If any exponent can decrease, this is not an infinite rule.
          self.infinite = False
          break

  def __repr__(self):
    return ("General Rule %s\nVar List: %s\nMin List: %s\nResult List: %s\n"
            "Steps %s Loops %s"
            % (self.name, self.var_list, self.min_list, self.result_list,
               self.num_steps, self.num_loops))

class Collatz_Rule(Rule):
  """General rule that only applies if exponents have certain parity."""
  def __init__(self, var_list, coef_list, parity_list, min_list,
               result_list, num_steps, num_loops):
    # *_lists are parallel lists for each exponent in the configuration.
    # If one exponent goes from 2k+1 -> 3k+5 for all 2k+1 >= 5, then
    # var = k, coef = 2, parity = 1, min = 5 and result = 3k+5
    assert len(var_list) == len(coef_list) == len(parity_list) == len(min_list)
    self.var_list = var_list
    self.coef_list = coef_list
    self.parity_list = parity_list
    self.min_list = min_list

    self.result_list = result_list
    self.num_steps = num_steps
    self.num_loops = num_loops
    self.name = ""  # Name will be set in Collatz_Rule_Group.

    self.num_uses = 0

    # Is this rule increasing? If all Collatz rules in a group are increasing
    # then the group is infinite.
    self.increasing = True
    for var, coef, parity, result in zip(self.var_list, self.coef_list,
                                         self.parity_list, self.result_list):
      if var:  # If this exponent changes in this rule (has a variable)
        start_expr = coef * VariableToExpression(var) + parity
        if is_scalar(result) or not result.always_greater_than(start_expr):
          # If any exponents can decrease, this isn't an increasing rule.
          self.infinite = False
          break

  def __repr__(self):
    return ("Collatz Rule %s\n"
            "Var List: %s\n"
            "Coef List: %s\n"
            "Parity List: %s\n"
            "Min List: %s\n"
            "Result List: %s\n"
            "Steps %s Loops %s"
            % (self.name, self.var_list, self.coef_list, self.parity_list,
               self.min_list, self.result_list, self.num_steps, self.num_loops))

class Collatz_Rule_Group(Rule):
  """
  A set of Collatz_Rules which all come from the same stripped config,
  but have different initial parities.
  """
  def __init__(self, subrule, rule_num):
    self.coef_list = subrule.coef_list
    self.total_subrules = 1  # = product(self.coef_list)
    for coef in self.coef_list:
      if coef:
        self.total_subrules *= coef

    self.rules = { tuple(subrule.parity_list): subrule }
    self.infinite = False
    # TODO(shawn): Check if this partial rule is infinite, say: 1^2k -> 1^2k+2

    self.name = str(rule_num)
    subrule.name = "%s.%d" % (self.name, len(self.rules))
    self.num_uses = 0

  def add_rule(self, rule):
    """Add a Collatz_Rule to this group."""
    if rule.coef_list != self.coef_list:
      # Note: This happens, for example for Machines/3x3-Collatz-Breaker,
      # where one path proves the rule for 2k + 0 and another for 4k + 3.
      # TODO(sligocki): Deal with these situations.
      #Log.error (rule, self.rules)
      return
    assert tuple(rule.parity_list) not in self.rules, (rule, self.rules)
    self.rules[tuple(rule.parity_list)] = rule
    rule.name = "%s.%d" % (self.name, len(self.rules))
    # We only say a Collatz Group is infinite if we have all the subrules.
    # TODO(shawn): Check if partial rule groups are infinite.
    if len(self.rules) == self.total_subrules:
      non_increasing_rules = [rule for rule in self.rules.values()
                              if not rule.increasing]
      if len(non_increasing_rules) == 0:
        self.infinite = True

  def __repr__(self):
    s = "Collatz Rule Group %s\n" % self.name
    for rule in self.rules.values():
      s += str(rule).replace("\n", "\n  ")
      s += "\n\n"
    return s

class Limited_Diff_Rule(Rule):
  """A Diff_Rule that only refers to a sub-section of the tape."""
  def __init__(self, initial_tape, left_dist, right_dist, diff_tape, initial_state, num_steps, num_loops, rule_num):
    # TODO: Use basic lists instead of tapes, we never use the symbols.
    # TODO: Have a variable list and a min list instead of packing both
    # into init_tape.
    # TODO: Or maybe we don't even need variables, we could just have the
    # things that depend on variables index directly into the tapes?
    # TODO: Actually, variables only appear in num_steps, so we don't even
    # need them if we are not computing steps.
    self.initial_tape = initial_tape
    self.left_dist = left_dist
    self.right_dist = right_dist
    self.rule_len = left_dist + right_dist
    self.diff_tape = diff_tape
    self.num_steps = num_steps
    self.initial_state = initial_state
    self.num_loops = num_loops
    self.name = str(rule_num)  # Unique identifier.
    self.num_uses = 0  # Number of times this rule has been applied.

  def __repr__(self):
    return ("Limited Diff Rule %s\nInitial Config: %s (%d,%d)\nDiff Config:    %s\nSteps: %s, Loops: %s"
            % (self.name, self.initial_tape.print_with_state(self.initial_state),self.left_dist,self.right_dist,self.diff_tape.print_with_state(self.initial_state), self.num_steps,
               self.num_loops))

# TODO: Try out some other stripped_configs
def stripped_info(block):
  """Get an abstraction of a tape block. We try to prove rules between
  configuration which have the same abstraction.
  """
  if block.num == 1:
    return block.symbol, 1
  else:
    return block.symbol

def strip_config(state, dir, tape):
  """"Return a generalized configuration removing the non-1 repetition counts from the tape."""
  # Optimization: Strip off Infinity blocks before we run the map (see tape[x][1:]).
  # Turns out Infinity.__cmp__ is expensive when run millions of times.
  # It used to spend up to 25% of time here.
  # TODO: This map is expensive upwards of 10% of time is spend here.
  return (state, dir, tuple(map(stripped_info, tape[0][1:])),
                      tuple(map(stripped_info, tape[1][1:])))

class Past_Config(object):
  """A record of info from past instances of a stripped_config."""
  def __init__(self):
    self.times_seen = 0
    self.last_loop_num = None
    self.last_delta = None
    #self.delta_loops = set()

  def __repr__(self):
    return repr(self.__dict__)

  def log_config(self, step_num, loop_num):
    """Decide whether we should try to prove a rule.

    Currently, we try to prove a rule we've seen happen twice (not necessarily
    consecutive) with the same num of loops (last_delta or delta_loops).
    """
    # First time we see stripped_config, store loop_num.
    if self.last_loop_num == None:
      self.last_loop_num = loop_num
      self.times_seen += 1
      return False

    # Next store last_delta. If we have a last_delta but it hasn't repeated,
    # then update the new delta. (Note: We can only prove rules that take
    # the same number of loops each time.)
    delta = loop_num - self.last_loop_num
    if not self.last_delta or self.last_delta != delta:
      self.last_delta = delta
      #self.delta_loops = set()
      #self.delta_loops.add(delta)
      self.last_loop_num = loop_num
      self.times_seen += 1
      return False

    # Now we can finally try a proof.
    return True

class Proof_System(object):
  """Stores past information, looks for patterns and tries to prove general
  rules when it finds patterns.
  """
  def __init__(self, machine, options, verbose_prefix):
    assert isinstance(options, optparse.Values)

    self.machine = machine
    self.options = options
    # Should we try to prove recursive rules? (Rules which use previous rules as steps.)
    self.recursive = options.recursive
    # Allow Collatz-style recursive rules. These are rules which depend upon
    # the parity (or remainder mod n) of exponents.
    # E.g. 1^(2k+1) 0 2 B>  -->  1^(3k+3) 0 2 B>
    # Note: Very experimental, may well break your simulation.
    self.allow_collatz = options.allow_collatz
    self.compute_steps = options.compute_steps
    self.verbose = options.verbose_prover  # Step-by-step state printing
    self.verbose_prefix = verbose_prefix
    # Memory of past stripped configurations with enough extra information to
    # try to prove rules. Set to None to disable proving new rules (for example
    # if this is a recursive proof system being used simply to apply rules).
    self.past_configs = defaultdict(Past_Config)
    # Colection of proven rules indexed by stripped configurations.
    self.rules = {}
    self.rule_num = 1

    # After proving a part of a Collatz rule, do not try to log any other
    # rules until we have a chance to prove the rest of the Collatz rule.
    self.pause_until_loop = None

    self.max_num_reps = options.max_num_reps

    # Stat
    self.num_loops = 0
    self.num_recursive_rules = 0
    self.num_collatz_rules = 0
    self.num_failed_proofs = 0
    # TODO: Record how many steps are taken by recursive rules in simulator.

  def print_this(self, *args):
    """Print with prefix."""
    print self.verbose_prefix,
    for arg in args:
      print arg,
    print

  def delete_rule(self, name):
    found = False

    if self.options.limited_rules:
      for key, rules in self.rules.iteritems():
        for rule in rules:
          if name == rule.name:
            rules.remove(rule)
            found = True
            break

      if not found:
        print "\nRule %s not found\n" % (name,)
    else:
      for key, rule in self.rules.iteritems():
        if name == rule.name:
          del self.rules[key]
          found = True
          break

      if not found:
        print "\nRule %s not found\n" % (name,)

  def rename_rule(self, src, dest):
    found_src  = False
    found_dest = False

    if self.options.limited_rules:
      for key, rules in self.rules.iteritems():
        for rule in rules:
          if src == rule.name:
            found_src = True
          if dest == rule.name:
            found_dest = True

      if not found_src:
        print "\nRule %s not found\n" % (src,)
      elif found_dest:
        print "\nRule %s already exists\n" % (dest,)
      else:
        for key, rules in self.rules.iteritems():
          for rule in rules:
            if src == rule.name:
              rule.name = dest
    else:
      for key, rule in self.rules.iteritems():
        if src == rule.name:
          key_src = key
          found_src = True
        if dest == rule.name:
          found_dest = True

      if not found_src:
        print "\nRule %s not found\n" % (src,)
      elif found_dest:
        print "\nRule %s already exists\n" % (dest,)
      else:
        self.rules[key_src].name = dest

  def print_rules(self, args=None):
    if self.options.limited_rules:
      rules = list(set([(rule.name, rule) for key in self.rules.keys() for rule in self.rules[key]]))
      sorted_rules = sorted(rules)
      found_rule = False
      for rule_name, rule in sorted_rules:
        if args:
          if rule.name != args:
            continue
        found_rule = True
        print
        self.print_this("Rule", rule.name)
        state = rule.initial_state
        self.print_this("Initial:", rule.initial_tape.print_with_state(state))
        self.print_this("Diff:", rule.diff_tape)
        self.print_this("Loops:", rule.num_loops, "Steps:", rule.num_steps)
        self.print_this("Num uses:", rule.num_uses)

      if found_rule:
        print
    else:
      sorted_keys = sorted([[self.rules[key].name, key] for key in self.rules.keys()])
      found_rule = False
      for rule_name, key in sorted_keys:
        rule = self.rules[key]
        if args:
          if rule.name != args:
            continue
        found_rule = True
        print
        self.print_this("Rule", rule.name)
        state = rule.initial_state
        self.print_this("Initial:", rule.initial_tape.print_with_state(state))
        self.print_this("Diff:", rule.diff_tape)
        self.print_this("Loops:", rule.num_loops, "Steps:", rule.num_steps)
        self.print_this("Num uses:", rule.num_uses)

      if found_rule:
        print

  def log(self, tape, state, step_num, loop_num):
    """
    Log this configuration into the memory and check if it is similar to a
    past one. Returned boolean answers question: Rule applies?
    """
    # Stores state, direction pointed, and list of symbols on tape.
    # Note: we ignore the number of repetitions of these sequences so that we
    #   can get a very general view of the tape.
    stripped_config = strip_config(state, tape.dir, tape.tape)
    full_config = (state, tape, step_num, loop_num)

    ## If we're already proven a rule for this stripped_config, try to apply it.
    # TODO: stripped_config in self.rules.
    if self.options.limited_rules:
      (state, dir, stripped_tape_left, stripped_tape_right) = stripped_config

      stripped_tape_left = (Tape.Repeated_Symbol(0,-1),) + stripped_tape_left
      stripped_configs_left = [(0, state, dir, stripped_tape_left[-i:], i) for i in xrange(1,len(stripped_tape_left)+1)]

      list_left = [rule for config in stripped_configs_left if config in self.rules for rule in self.rules[config]]

      stripped_tape_right = (Tape.Repeated_Symbol(0,-1),) + stripped_tape_right
      stripped_configs_right = [(1, state, dir, stripped_tape_right[-i:], i) for i in xrange(1,len(stripped_tape_right)+1)]

      list_right = [rule for config in stripped_configs_right if config in self.rules for rule in self.rules[config]]

      rules = list(set(list_left) & set(list_right))

      for rule in rules:
        is_good, res = self.apply_rule(rule, full_config)
        if is_good:
          trans, large_delta = res
          # Optimization: If we apply a rule and we are not trying to perform
          # recursive proofs, clear past configuration memory.
          # Likewise, even normal recursive proofs cannot use every subrule
          # as a step. Specifically, if there are any negative deltas other
          # than -1, we cannot apply the rule in a proof because
          # e.g. (x + 3 // 2) is unresolvable. However, Collatz proofs can
          # include such large negative deltas.
          if not self.recursive or (large_delta and not self.allow_collatz):
            if self.past_configs is not None:
              self.past_configs.clear()
          rule.num_uses += 1
          assert len(trans) == 4
          return trans
        # return False, None, None, None
    else:
      if stripped_config in self.rules:
        rule = self.rules[stripped_config]
        is_good, res = self.apply_rule(rule, full_config)
        if is_good:
          trans, large_delta = res
          # Optimization: If we apply a rule and we are not trying to perform
          # recursive proofs, clear past configuration memory.
          # Likewise, if we apply a rule with a negative diff < -1 and we
          # don't allow collatz rules, clear past configs.
          if not self.recursive or (large_delta and not self.allow_collatz):
            if self.past_configs is not None:
              self.past_configs.clear()
          rule.num_uses += 1
          assert len(trans) == 4
          return trans
        if res != UNPROVEN_PARITY:
          return False, None, None, None

    # If we are not trying to prove new rules, quit.
    if self.past_configs is None:
      # TODO: Just return False for fail and object for success.
      return False, None, None, None

    # Otherwise log it into past_configs and see if we should try and prove
    # a new rule.
    if (self.pause_until_loop == None or loop_num >= self.pause_until_loop or
        stripped_config in self.past_configs):
      past_config = self.past_configs[stripped_config]
      if past_config.log_config(step_num, loop_num):
        # We see enough of a pattern to try and prove a rule.
        rule = self.prove_rule(stripped_config, full_config,
                               loop_num - past_config.last_loop_num)
        if not rule:
          self.num_failed_proofs += 1
        else:  # If we successfully proved a rule:
          # Collatz_Rules need to be stored inside Collatz_Rule_Groups.
          if isinstance(rule, Collatz_Rule):
            self.pause_until_loop = loop_num + 100 * rule.num_loops
            if stripped_config in self.rules:
              group = self.rules[stripped_config]
              if not group.add_rule(rule):
                if self.verbose:
                  self.print_this("++ Collatz Rule doesn't match Group ++")
                  self.print_this("Rule:", str(rule).replace(
                      "\n", "\n" + self.verbose_prefix + "       "))
                  self.print_this("Group:", str(group).replace(
                      "\n", "\n" + self.verbose_prefix + "        "))
            else:
              group = Collatz_Rule_Group(rule, self.rule_num)
            rule = group

          # Remember rule.
          if isinstance(rule, Limited_Diff_Rule):
            (state, dir, stripped_tape_left, stripped_tape_right) = stripped_config
            stripped_tape_left = (Tape.Repeated_Symbol(0,-1),) + stripped_tape_left
            stripped_config_left  = (0, state, dir, stripped_tape_left[-rule.left_dist:],  rule.left_dist )

            stripped_tape_right = (Tape.Repeated_Symbol(0,-1),) + stripped_tape_right
            stripped_config_right = (1, state, dir, stripped_tape_right[-rule.right_dist:], rule.right_dist)

            if stripped_config_left in self.rules:
              self.rules[stripped_config_left].append(rule)
            else:
              self.rules[stripped_config_left] = [rule,]

            if stripped_config_right in self.rules:
              self.rules[stripped_config_right].append(rule)
            else:
              self.rules[stripped_config_right] = [rule,]

            self.rule_num += 1
          else:
            self.rules[stripped_config] = rule
            self.rule_num += 1

          # Clear our memory. We cannot use it for future rules because the
          # number of steps will be wrong now that we have proven this rule.
          #
          # Note: We save the past_config for this stripped_config so that
          # information for Collatz rules is not lost.
          saved = self.past_configs[stripped_config]
          self.past_configs.clear()
          saved.last_loop_num = None
          self.past_configs[stripped_config] = saved

          # Try to apply transition
          is_good, res = self.apply_rule(rule, full_config)
          if is_good:
            trans, large_delta = res
            rule.num_uses += 1
            assert len(trans) == 4
            return trans

    return False, None, None, None

  def prove_rule(self, stripped_config, full_config, delta_loop):
    """Try to prove a general rule based upon specific example.

    Returns rule if successful or None.
    """
    # Unpack configurations
    new_state, new_tape, new_step_num, new_loop_num = full_config

    if self.verbose:
      print
      self.print_this("** Testing new rule **")
      self.print_this("Original config:", new_tape.print_with_state(new_state))
      self.print_this("Start loop:", new_loop_num, "Loops:", delta_loop)

    # Create the limited simulator with limited or no prover.
    new_options = copy.copy(self.options)
    new_options.recursive = False
    new_options.prover = False  # We'll create our own prover if needed.
    new_options.verbose_prover=False
    new_options.verbose_simulator=self.verbose
    gen_sim = Simulator.Simulator(self.machine,
                                  new_options,
                                  init_tape=False,
                                  verbose_prefix=self.verbose_prefix + "  ")
    gen_sim.state = new_state
    gen_sim.step_num = ConstantToExpression(0)

    # If prover can run recursively, we let it simulate with a lazy prover.
    # That is, one that cannot prove new rules, only use already proven ones.
    if self.recursive:
      gen_sim.prover = copy.copy(self)
      gen_sim.prover.past_configs = None
      gen_sim.prover.verbose_prefix = gen_sim.verbose_prefix + "  "

    # Create a new tape which we will use to simulate general situation.
    gen_sim.tape = new_tape.copy()
    min_val = {} # Notes the minimum value exponents with each unknown take.
    for direction in range(2):
      offset = len(gen_sim.tape.tape[direction])
      for block in gen_sim.tape.tape[direction]:
        block.id = offset
        offset -= 1
        # Generalize, eg. (abc)^5 -> (abc)^(n+5)
        # Blocks with one rep are not generalized, eg. (abc)^1 -> (abc)^1
        if block.num not in (Tape.INF, 1):
          x = Variable()
          x_expr = VariableToExpression(x)
          block.num += x_expr
          min_val[x] = block.num.const
    initial_tape = gen_sim.tape.copy()
    gen_sim.dir = gen_sim.tape.dir

    # Run the simulator
    gen_sim.verbose_print()
    gen_sim.step()
    dist = [1, 1]
    cur_dir = gen_sim.tape.dir
    cur_dist = gen_sim.tape.tape[cur_dir][-1].id
    if cur_dist and cur_dist > dist[cur_dir]:
      dist[cur_dir] = cur_dist
    self.num_loops += 1
    #for i in xrange(delta_loop):
    while gen_sim.num_loops < delta_loop:
      # We cannot step onto/over a block with 0 repetitions.
      block = gen_sim.tape.get_top_block()
      if isinstance(block.num, Algebraic_Expression) and block.num.const <= 0:
        # TODO: A more sophisticated system might try to make this block
        # fixed sized.
        # For now we just fail. It may not be worth implimenting this anyway
        if self.verbose:
          print
          self.print_this("** Failed: Exponent below min **")
          self.print_this(gen_sim.tape.print_with_state(gen_sim.state))
          print
        return False
      gen_sim.step()
      cur_dir = gen_sim.tape.dir
      cur_dist = gen_sim.tape.tape[cur_dir][-1].id
      if cur_dist and cur_dist > dist[cur_dir]:
        dist[cur_dir] = cur_dist
      self.num_loops += 1
      # TODO(shawn): Perhaps we should check in applying a rule failed this
      # step and if so cancel the proof?

      if gen_sim.replace_vars:
        assert self.allow_collatz
        # Replace the variables in various places.
        for init_block in initial_tape.tape[0]+initial_tape.tape[1]:
          if isinstance(init_block.num, Algebraic_Expression):
            init_block.num = init_block.num.substitute(gen_sim.replace_vars)
        for old_var, new_expr in gen_sim.replace_vars.items():
          new_var = new_expr.variable()
          min_val[new_var] = min_val[old_var]
          del min_val[old_var]
        # TODO(shawn): We might not want to clear this ...
        gen_sim.replace_vars.clear()

      if gen_sim.op_state is not Turing_Machine.RUNNING:
        if self.verbose:
          print
          self.print_this("** Failed: Machine stopped running **")
          print
        return False
      # Update min_val for each expression.
      # TODO: We only need to update for the blocks on each side of head.
      # TODO: Better yet, build these checks into the data type!
      for dir in range(2):
        for block in gen_sim.tape.tape[dir]:
          if isinstance(block.num, Algebraic_Expression):
            if len(block.num.terms) == 1:
              x = block.num.variable()
              min_val[x] = min(min_val[x], block.num.const)
            # If more than one variable is clumped into a single term,
            # it will fail.
            elif len(block.num.terms) > 1:
              if self.verbose:
                print
                self.print_this("** Failed: Multiple vars in one term **")
                self.print_this(gen_sim.tape)
                print
              return False

    # Make sure finishing tape has the same stripped config as original.
    gen_stripped_config = strip_config(gen_sim.state, gen_sim.tape.dir,
                                       gen_sim.tape.tape)
    if gen_stripped_config != stripped_config:
      if self.verbose:
        print
        self.print_this("** Failed: Config mismatch **")
        self.print_this(gen_sim.tape)
        self.print_this(gen_stripped_config)
        self.print_this(stripped_config)
        print
      return False

    # If machine has run delta_steps without error, it is a general rule.
    # Compute the diff_tape and find out if this is a recursive rule.
    # TODO: There should be a better way to find out if this is recursive.
    rule_type = Diff_Rule
    #diff_tape = new_tape.copy()
    diff_tape = gen_sim.tape.copy()
    for dir in range(2):
      for diff_block, initial_block in zip(diff_tape.tape[dir],
                                           initial_tape.tape[dir]):
        if diff_block.num != Tape.INF:
          diff_block.num -= initial_block.num
          if isinstance(diff_block.num, Algebraic_Expression):
            coef = initial_block.num.get_coef()
            if coef != None and coef != 1:
              # TODO(shawn): We should record this during simulation time.
              rule_type = Collatz_Rule
              # TODO(shawn): If the diff is constant (say 2x+1 -> 2x+3),
              # perhaps we could prove a diff-rule?
            else:
              if diff_block.num.is_const():
                diff_block.num = diff_block.num.const
              else:
                assert coef != None, (initial_block, initial_tape)
                rule_type = General_Rule

    if rule_type == General_Rule:
      # TODO: Don't do all the work above if we're not going to use it
      # Get everything in the right form for a General_Rule.
      var_list = []
      min_list = []
      assignment = {}
      for init_block in initial_tape.tape[0]+initial_tape.tape[1]:
        if isinstance(init_block.num, Algebraic_Expression):
          x = init_block.num.variable_restricted()
          var_list.append(x)
          min_list.append(init_block.num.const - min_val[x] + 1)
          # Hackish: If exponent was x + 5 we want to replace all x with x - 5.
          # TODO: Make nicer.
          assignment[x] = init_block.num - 2*init_block.num.const
        else:
          var_list.append(None)
          min_list.append(init_block.num)

      # TODO: result_list = []
      result_tape = gen_sim.tape
      # Fix up result_tape to by applying variable substitution.
      for result_block in result_tape.tape[0]+result_tape.tape[1]:
        if isinstance(result_block.num, Algebraic_Expression):
          result_block.num = result_block.num.substitute(assignment)

      # Fix num_steps.
      if self.compute_steps:
        num_steps = gen_sim.step_num.substitute(assignment)
      else:
        num_steps = 0

      self.num_recursive_rules += 1
      rule = General_Rule(var_list, min_list, result_tape, num_steps,
                          gen_sim.num_loops, self.rule_num)

      if self.verbose:
        print
        self.print_this("** New recursive rule proven **")
        self.print_this(str(rule).replace("\n", "\n " + self.verbose_prefix))
        print

      return rule
    elif rule_type == Collatz_Rule:
      # Get everything in the right form for a Collatz_Rule.
      var_list = []
      coef_list = []
      parity_list = []
      min_list = []
      assignment = {}

      for init_block in initial_tape.tape[0]+initial_tape.tape[1]:
        if isinstance(init_block.num, Algebraic_Expression):
          var = init_block.num.variable()
          coef = init_block.num.get_coef()
          const = init_block.num.const
          parity = const % coef

          var_list.append(var)
          assert coef != None
          coef_list.append(coef)
          parity_list.append(parity)
          min_list.append(const)

          # Update var so that: ceof * var + const -> coef * var + parity
          assignment[var] = VariableToExpression(var) - (const // coef)
          assert (init_block.num.substitute(assignment) ==
                  coef * VariableToExpression(var) + parity)
        else:
          var_list.append(None)
          coef_list.append(None)
          parity_list.append(None)
          min_list.append(init_block.num)

      result_list = []
      result_tape = gen_sim.tape
      for result_block in result_tape.tape[0]+result_tape.tape[1]:
        if isinstance(result_block.num, Algebraic_Expression):
          result_list.append(result_block.num.substitute(assignment))
        else:
          result_list.append(result_block.num)

      # Fix num_steps.
      if self.compute_steps:
        num_steps = gen_sim.step_num.substitute(assignment)
      else:
        num_steps = 0

      self.num_collatz_rules += 1
      rule = Collatz_Rule(var_list, coef_list, parity_list, min_list,
                          result_list, num_steps, gen_sim.num_loops)

      if self.verbose:
        print
        self.print_this("** New Collatz rule proven **")
        self.print_this(str(rule).replace("\n", "\n " + self.verbose_prefix))
        print

      return rule
    else:
      # Else if a normal diff rule:
      # Tighten up rule to be as general as possible
      # (e.g. by replacing x+5 with x+1 if the rule holds for 1).
      replaces = {}
      for dir in range(2):
        for init_block in initial_tape.tape[dir]:
          if isinstance(init_block.num, Algebraic_Expression):
            x = init_block.num.variable_restricted()
            new_value = VariableToExpression(x) - min_val[x] + 1
            init_block.num = init_block.num.substitute({x: new_value})
            replaces[x] = new_value
      # Fix diff_tape.  # TODO: rm, only happens for recursive_rules
      for dir in range(2):
        for diff_block in diff_tape.tape[dir]:
          if isinstance(diff_block.num, Algebraic_Expression):
            diff_block.num = diff_block.num.substitute(replaces)
      # Fix num_steps.
      if self.compute_steps:
        num_steps = gen_sim.step_num.substitute(replaces)
      else:
        num_steps = 0

      # Cast num_steps as an Algebraic Expression (if it somehow got through
      # as simply an int)
      if not isinstance(num_steps, Algebraic_Expression):
        num_steps = ConstantToExpression(num_steps)

      if self.options.limited_rules:
        left_dist  = dist[0]
        right_dist = dist[1]

        initial_tape.tape[0] = initial_tape.tape[0][-left_dist:]
        initial_tape.tape[1] = initial_tape.tape[1][-right_dist:]

        diff_tape.tape[0] = diff_tape.tape[0][-left_dist:]
        diff_tape.tape[1] = diff_tape.tape[1][-right_dist:]

        rule = Limited_Diff_Rule(initial_tape, left_dist, right_dist, diff_tape, new_state, num_steps, gen_sim.num_loops, self.rule_num)
      else:
        rule = Diff_Rule(initial_tape, diff_tape, new_state, num_steps, gen_sim.num_loops, self.rule_num)

      if self.verbose:
        print
        self.print_this("** New rule proven **")
        self.print_this(str(rule).replace("\n", "\n " + self.verbose_prefix))
        print

      return rule

  def apply_rule(self, rule, start_config):
    """Try to apply a rule to a given configuration."""
    # TODO: Currently this returns a new tape and does not mutate the input.
    # Is that necessary, would it be worth it to mutate the input config
    # in-place?
    if self.verbose:
      start_state, start_tape, start_step_num, start_loop_num = start_config
      print
      self.print_this("++ Applying Rule ++")
      self.print_this("Loop:", start_loop_num, "Rule ID:", rule.name)
      self.print_this("Rule:", str(rule).replace("\n",
                                                  "\n" + self.verbose_prefix +
                                                  "       "))
      self.print_this("Config:", start_tape.print_with_state(start_state))

    if isinstance(rule, Diff_Rule):
      return self.apply_diff_rule(rule, start_config)
    elif isinstance(rule, General_Rule):
      return self.apply_general_rule(rule, start_config)
    elif isinstance(rule, Collatz_Rule_Group):
      return self.apply_collatz_rule(rule, start_config)
    elif isinstance(rule, Limited_Diff_Rule):
      start_state, start_tape, start_step_num, start_loop_num = start_config

      limited_start_tape = start_tape.copy()

      save_left  = limited_start_tape.tape[0][:-rule.left_dist]
      save_right = limited_start_tape.tape[1][:-rule.right_dist]

      limited_start_tape.tape[0] = limited_start_tape.tape[0][-rule.left_dist:]
      limited_start_tape.tape[1] = limited_start_tape.tape[1][-rule.right_dist:]

      limited_start_config = (start_state, limited_start_tape, start_step_num, start_loop_num)

      success, other = self.apply_diff_rule(rule, limited_start_config)

      if success:
        (machine_state, final_tape, diff_steps, replace_vars), large_delta = other

        if machine_state == Turing_Machine.RUNNING:
          final_tape.tape[0] = save_left  + final_tape.tape[0]
          final_tape.tape[1] = save_right + final_tape.tape[1]

          other = ((machine_state, final_tape, diff_steps, replace_vars), large_delta)

      return success, other
    else:
      assert False, (type(rule), repr(rule))

  def apply_diff_rule(self, rule, start_config):
    ## Unpack input
    new_state, new_tape, new_step_num, new_loop_num = start_config
    new_tape = new_tape.copy()  # Make a clean copy that we can edit here.

    ## Calculate number of repetitions allowable and other tape-based info.
    num_reps = None
    init_value = {}
    delta_value = {}
    # large_delta == True  iff there is a negative delta != -1
    # We keep track because even recursive proofs cannot contain rules
    # with large_deltas, unless we allow Collatz proofs.
    large_delta = False
    has_variable = False
    replace_vars = {}  # Dict of variable substitutions made by Collatz applier.
    for dir in range(2):
      for init_block, diff_block, new_block in zip(rule.initial_tape.tape[dir], rule.diff_tape.tape[dir], new_tape.tape[dir]):
        # The constant term in init_block.num represents the minimum
        # required value.
        if isinstance(init_block.num, Algebraic_Expression):
          # Calculate the initial and change in value for each variable.
          x = init_block.num.variable_restricted()
          # init_block.num.const == min_value for this exponent.
          init_value[x] = new_block.num - init_block.num.const
          if (not isinstance(init_value[x], Algebraic_Expression) and
              init_value[x] < 0):
            if self.verbose:
              self.print_this("++ Current config is below rule minimum ++")
              self.print_this("Config block:", new_block)
              self.print_this("Rule initial block:", init_block)
              self.print_this("")
            return False, 1
          delta_value[x] = diff_block.num
          assert(isinstance(delta_value[x], (int, long)))
          # If this block's repetitions will be depleted during this transition,
          #   count the number of repetitions that it can allow while staying
          #   above the minimum requirement.
          if delta_value[x] < 0:
            if delta_value[x] != -1:
              large_delta = True
            if num_reps is None:
              if (isinstance(init_value[x], Algebraic_Expression) and
                  delta_value[x] != -1):
                if self.allow_collatz:
                  if not init_value[x].is_var_plus_const():
                    if self.verbose:
                      self.print_this("++ Unsupported big-delta on Collatz expression ++")
                      self.print_this("%r // %r"
                                      % (init_value[x], -delta_value[x]))
                      self.print_this("")
                    return False, 2
                  else:
                    # TODO(shawn): Deal with Collatz expressions here.
                    # We should have something like (x + 12)
                    old_var = init_value[x].variable_restricted()  # x
                    old_const = init_value[x].const    # 12
                    new_var = NewVariableExpression()  # k
                    # 1) Record that we are replacing x with 3k.
                    replace_vars[old_var] = new_var * -delta_value[x]
                    # Update all the tape cells right away.
                    for dir in range(2):
                      for block in new_tape.tape[dir]:
                        if isinstance(block.num, Algebraic_Expression):
                          block.num = block.num.substitute(replace_vars)
                    # Update all initial values as well.
                    for y in init_value.keys():
                      if isinstance(init_value[y], Algebraic_Expression):
                        init_value[y] = init_value[y].substitute(replace_vars)
                    # 2) num_reps = (3k + 12) // 3 + 1 = k + (12//3) + 1
                    num_reps = new_var + (old_const // -delta_value[x])  + 1
                    if self.verbose:
                      self.print_this("++ Experimental Collatz diff ++")
                      self.print_this("Substituting:", old_var, "=",
                                      replace_vars[old_var])
                      self.print_this("From: num_reps = (%r // %r)  + 1"
                                      % (init_value[x], -delta_value[x]))
                      self.print_this("")
                else:
                  if self.verbose:
                    self.print_this("++ Collatz diff ++")
                    self.print_this("From: num_reps = (%r // %r)  + 1"
                                    % (init_value[x], -delta_value[x]))
                    self.print_this("")
                  return False, 2
              else:
                # First one is safe.
                # For example, if we have a rule:
                #   Initial: 0^Inf 2^(d + 1) (0) B> 2^(f + 2) 0^Inf
                #   Diff:    0^Inf 2^1 (0) B> 2^-1 0^Inf
                # then:
                #   0^Inf 2^3  (0)B> 2^(s + 11) 0^Inf
                # goes to:
                #   0^Inf 2^(s + 12)  (0)B> 2^2 0^Inf
                num_reps = (init_value[x] // -delta_value[x])  + 1
            else:
              if (not isinstance(init_value[x], Algebraic_Expression) and
                  not isinstance(num_reps, Algebraic_Expression)):
                # As long as init_value[x] >= 0 we can apply proof
                num_reps = min(num_reps, (init_value[x] // -delta_value[x])  + 1)
              else:
                # Example Rule:
                #   Initial: 0^Inf 2^a+1 0^1 1^b+3 B> 0^1 1^c+1 0^Inf
                #   Diff:    0^Inf 2^-1  0^0 1^+2  B> 0^0 1^-1  0^Inf
                # Applied to tape:
                #   0^Inf 2^d+5 0^1 1^3 B> 0^1 1^e+3 0^Inf
                # We shoud apply the rule either d+4 or e+2 times depending
                # on which is smaller. Too complicated, we fail.
                if self.verbose:
                  self.print_this("++ Multiple negative diffs for expressions ++")
                  self.print_this("Config block:", new_block)
                  self.print_this("Rule initial block:", init_block)
                  self.print_this("Rule diff block:", diff_block)
                  self.print_this("Config tape:", new_tape)
                  self.print_this("Initial tape:", rule.initial_tape)
                  self.print_this("Rule diff tape:", rule.diff_tape)
                  self.print_this("")
                return False, "Multiple_Diff"

    # If none of the diffs are negative, this will repeat forever.
    if num_reps is None:
      if self.verbose:
        self.print_this("++ Rules applies infinitely ++")
        print
      return True, ((Turing_Machine.INF_REPEAT, None, None, {}), large_delta)

    # If we cannot even apply this transition once, we're done.
    if (not isinstance(num_reps, Algebraic_Expression) and
        num_reps <= 0):
      if self.verbose:
        self.print_this("++ Cannot even apply transition once ++")
        print
      return False, 3

    ## Determine number of base steps taken by applying rule.
    if self.compute_steps:
      # Effect of the constant factor:
      diff_steps = rule.num_steps.const * num_reps
      # Effects of each variable in the formula:
      for term in rule.num_steps.terms:
        assert len(term.vars) == 1
        coef = term.coef; x = term.vars[0].var
        # We don't factor out the coef, because it might make this work
        # better for some recursive rules.
        try:
          diff_steps += series_sum(coef * init_value[x], coef * delta_value[x], num_reps)
        except TypeError:
          if self.verbose:
            self.print_this("++ Cannot divide expression by 2 ++")
            print
          return False, 4
    else:
      diff_steps = 0 # TODO: Make it None instead of a lie

    ## Alter the tape to account for applying rule.
    return_tape = new_tape.copy()
    for dir in range(2):
      for diff_block, return_block in zip(rule.diff_tape.tape[dir],
                                          return_tape.tape[dir]):
        if return_block.num is not Tape.INF:
          return_block.num += num_reps * diff_block.num
          if isinstance(return_block.num, Algebraic_Expression) and \
                return_block.num.is_const():
            return_block.num = return_block.num.const
      return_tape.tape[dir] = [x for x in return_tape.tape[dir] if x.num != 0]

    ## Return the pertinent info
    if self.verbose:
      self.print_this("++ Rule successfully applied ++")
      self.print_this("Times applied:", num_reps)
      self.print_this("Diff steps:", diff_steps)
      self.print_this("Resulting tape:",
                      return_tape.print_with_state(new_state))
      print
    return True, ((Turing_Machine.RUNNING, return_tape, diff_steps,
                   replace_vars), large_delta)

  # Diff rules can be applied any number of times in a single evaluation.
  # But we can only apply a general rule once at a time.
  # TODO: Get function to apply repeatedly in tight loop.
  def apply_general_rule(self, rule, start_config):
    # Unpack input
    start_state, start_tape, start_step_num, start_loop_num = start_config

    large_delta = True  # Not editted in this function.
    # Current list of all block exponents. We will update it in place repeatedly
    # rather than creating new tapes.
    current_list = [block.num for block in start_tape.tape[0] + start_tape.tape[1]]

    # If this recursive rule is infinite.
    if rule.infinite and config_is_above_min(rule.var_list, rule.min_list,
                                             current_list):
      if self.verbose:
        self.print_this("++ Rule applies infinitely ++")
        print
      return True, ((Turing_Machine.INF_REPEAT, None, None, {}), large_delta)

    # Keep applying rule until we can't anymore.
    # TODO: Maybe we can use some intelligence when all negative rules are
    # constants becuase, then we know how many time we can apply the rule.
    success = False  # If we fail before doing anything, return false.
    num_reps = 0
    diff_steps = 0
    # Get variable assignments for this case and check minimums.
    assignment = {}
    while config_is_above_min(rule.var_list, rule.min_list, current_list, assignment) and num_reps < self.max_num_reps:
      if self.verbose:
        self.print_this(num_reps, current_list)

      # Apply variable assignment to update number of steps and tape config.
      if self.compute_steps:
        diff_steps += rule.num_steps.substitute(assignment)

      # TODO: Stop using substitute and make this a tuple-to-tuple function?
      next_list = [val.substitute(assignment)
                   if isinstance(val, Algebraic_Expression) else val
                   for val in rule.result_list]

      if next_list == current_list:
        return True, ((Turing_Machine.INF_REPEAT, None, None, {}), large_delta)
      else:
        current_list = next_list

      num_reps += 1
      success = True
      assignment = {}

    # We cannot apply rule any more.
    # Make sure there are no zero's in tape exponents.
    if success:
      tape = start_tape.copy()
      for block, current_val in zip(tape.tape[0] + tape.tape[1], current_list):
        block.num = current_val
      # TODO: Perhaps do this in one step?
      for dir in range(2):
        tape.tape[dir] = [x for x in tape.tape[dir] if x.num != 0]
      if self.verbose:
        self.print_this("++ Recursive rule applied ++")
        self.print_this("Times applied", num_reps)
        self.print_this("Resulting tape:", tape)
        print
      return True, ((Turing_Machine.RUNNING, tape, diff_steps, {}), large_delta)
    else:
      if self.verbose:
        self.print_this("++ Current config is below rule minimum ++")
        self.print_this("Config tape:", start_tape)
        self.print_this("Rule min vals:", min_list)
        print
      return False, 1

  def apply_collatz_rule(self, group, start_config):
    # Unpack input
    start_state, start_tape, start_step_num, start_loop_num = start_config

    large_delta = True  # Not edited in this function.
    # Current list of all block exponents. We will update it in place repeatedly
    # rather than creating new tapes.
    current_list = [block.num for block in start_tape.tape[0] + start_tape.tape[1]]

    # If this recursive rule is infinite.
    if group.infinite:
      # TODO(shawn): Check that we are above min! This is broken.
      #if config_is_above_min(rule.var_list, rule.min_list, current_list):
      if self.verbose:
        self.print_this("++ Rule applies infinitely ++")
        print
      return True, ((Turing_Machine.INF_REPEAT, None, None, {}), large_delta)

    # We cannot apply Collatz rules with general expressions.
    for val in current_list:
      if isinstance(val, Algebraic_Expression):
        if self.verbose:
          self.print_this("++ Cannot apply Collatz rule to expressions ++")
          self.print_this("Config tape:", start_tape)
          print
        return False, "Cannot apply Collatz rule to general expression"

    # Keep applying rule until we can't anymore.
    success = False  # If we fail before doing anything, return false.
    num_reps = 0
    diff_steps = 0
    # Get variable assignments for this case and check minimums.
    assignment = {}
    while True:
      # Print current state.
      if self.verbose:
        self.print_this(num_reps, current_list)

      # Find out which collatz sub-rule applies here (figure out parities).
      # Note that we already checked above that we current_list is scalar.
      parity_list = tuple(val % coef if coef else None
                          for val, coef in zip(current_list, group.coef_list))
      if parity_list not in group.rules:
        if self.verbose:
          # TODO(shawn): Just try to prove a rule for this parity right now.
          self.print_this("++ Reached unproven Collatz parity ++")
          self.print_this("Config tape:", start_tape)
          self.print_this("Parities:", parity_list)
          print
        reason = UNPROVEN_PARITY
        break
      rule = group.rules[parity_list]

      # Check that we are above the minimums and set assignments.
      above_min = True
      for current_val, var, coef, min_val in \
            zip(current_list, rule.var_list, rule.coef_list, rule.min_list):
        if var:
          # TODO(shawn): Allow rules with all parities.
          if current_val < min_val:
            above_min = False
            break
          assignment[var] = current_val // coef

      # TODO(shawn): This looks kludgey.
      if not above_min:
        reason = "Bellow min"
        break

      # Apply variable assignment to update number of steps and tape config.
      if self.compute_steps:
        diff_steps += rule.num_steps.substitute(assignment)
      # TODO: Stop using substitute and make this a tuple-to-tuple function?
      current_list = [val.substitute(assignment)
                      if isinstance(val, Algebraic_Expression) else val
                      for val in rule.result_list]
      num_reps += 1
      success = True
      assignment = {}

    # We cannot apply rule any more.
    # Make sure there are no zero's in tape exponents.
    if success:
      tape = start_tape.copy()
      for block, current_val in zip(tape.tape[0] + tape.tape[1], current_list):
        block.num = current_val
      # TODO: Perhaps do this in one step?
      for dir in range(2):
        tape.tape[dir] = [x for x in tape.tape[dir] if x.num != 0]
      if self.verbose:
        self.print_this("++ Collatz rule applied ++")
        self.print_this("Times applied", num_reps)
        self.print_this("Resulting tape:", tape)
        print
      return True, ((Turing_Machine.RUNNING, tape, diff_steps, {}), large_delta)
    else:
      if self.verbose and reason != UNPROVEN_PARITY:
        self.print_this("++ Current config is below rule minimum ++")
        self.print_this("Config tape:", start_tape)
        self.print_this("Rule min vals:", rule.min_list)
        print
      return False, reason

def config_is_above_min(var_list, min_list, current_list, assignment={}):
  """Tests if current_list is above min_list setting assignment along the way"""
  for var, min_val, current_val in zip(var_list, min_list, current_list):
    if current_val < min_val:
      return False
    assignment[var] = current_val
  return True

def series_sum(V0, dV, n):
  """Sums the arithmetic series V0, V0+dV, ... V0+(n-1)*dV."""
  # = sum(V0 + p*dV for p in range(n)) = V0*Sum(1) + dV*Sum(p)
  # = V0*n + dV*(n*(n-1)/2)
  # TODO: The '/' acts as integer division, this is dangerous. It should
  # always work out because either n or n-1 is even. However, if n is an
  # Algebraic_Expression, this is more complicated. We don't want to use
  # __truediv__ because then we'd get a float output for ints.
  # TODO: Don't crash when we get NotImplemented exception from
  # Algebraic_Expression.__div__.
  return V0*n + (dV*n*(n-1))/2
