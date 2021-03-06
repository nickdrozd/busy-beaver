#ifndef _CHAIN_SIMULATOR_H_
#define _CHAIN_SIMULATOR_H_

#include "Define.h"
#include "Turing_Machine.h"
#include "Tape.h"
#include "Proof_System.h"

class Chain_Simulator
{
  public:
    Chain_Simulator(shared_ptr<Turing_Machine> a_machine,
                    const bool               & a_recursive,
                    const bool               & a_prover);

    virtual ~Chain_Simulator();

    void seek(const INTEGER & a_cutoff);

    void step();

    INTEGER num_nonzero();

    void print(ostream & a_out) const;

    const char* m_inf_reason;

    INTEGER m_num_loops;

    INTEGER m_num_macro_moves;
    INTEGER m_steps_from_macro;

    INTEGER m_num_chain_moves;
    INTEGER m_steps_from_chain;

    INTEGER m_num_rule_moves;
    INTEGER m_steps_from_rule;

    shared_ptr<Turing_Machine> m_machine;

    TRANSITION    m_trans;
    Tape<INTEGER> m_tape;

    INTEGER   m_step_num;
    RUN_STATE m_op_state;

    Proof_System m_proof;
};

ostream& operator<<(ostream               & a_ostream,
                    const Chain_Simulator & a_sim);

#endif
