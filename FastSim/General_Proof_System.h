#ifndef _GENERAL_PROOF_SYSTEM_H_
#define _GENERAL_PROOF_SYSTEM_H_

#include "Define.h"
#include "Turing_Machine.h"
#include "Tape.h"
#include "Proof_System.h"
#include "Expression.h"

class General_Proof_System
{
  public:
    General_Proof_System();

    ~General_Proof_System();

    void define(shared_ptr<Turing_Machine> a_machine,
                const bool               & a_recursive);

    bool log(RUN_STATE            & a_run_state,
             Tape<Expression>     & a_new_tape,
             Expression           & a_num_steps,
             const GENERAL_CONFIG & a_full_config);

    bool compare(RULE                 & a_rule,
                 const GENERAL_CONFIG & a_old_config,
                 const GENERAL_CONFIG & a_new_config);

    bool applies(RUN_STATE            & a_run_state,
                 Tape<Expression>     & a_new_tape,
                 Expression           & a_num_steps,
                 bool                 & a_bad_delta,
                 const RULE           & a_rule,
                 const GENERAL_CONFIG & a_full_config);

    void strip_config(vector<int>            & a_stripped_config,
                      const STATE            & a_state,
                      const Tape<Expression> & a_tape);

    shared_ptr<Turing_Machine> m_machine;

    bool m_recursive;
    bool m_prove_new_rules;

    map<vector<int>,RULE>                m_proven_transitions;
    map<vector<int>,GENERAL_PAST_CONFIG> m_past_configs;

    bool m_is_defined;
};

#endif
