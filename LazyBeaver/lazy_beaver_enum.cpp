// Prototype script for quickly calculating Lazy Beaver by enumerating
// candidates and directly simulating them on an uncomressed tape.

#include <fstream>
#include <iostream>
#include <stack>
#include <string>

// #include <mpi.h>

#include "enumeration.h"
#include "turing_machine.h"


namespace lazy_beaver {

// Optimization parameters
// TODO(shawn or terry): These probably need to increase 5x2 case is spending
// 96% of time in communication.
#define MIN_NUM_JOBS_PER_BATCH 10
#define MAX_NUM_JOBS_PER_BATCH 25

#define DEFAULT_MAX_LOCAL_JOBS    30
#define DEFAULT_TARGET_LOCAL_JOBS 25

class WorkerWorkQueue {
  public:
    WorkerWorkQueue(int master_proc_num) {
      master_proc_num_ = master_proc_num;

      max_queue_size_    = DEFAULT_MAX_LOCAL_JOBS;
      target_queue_size_ = DEFAULT_TARGET_LOCAL_JOBS;
    }

    ~WorkerWorkQueue() {
    }

    TuringMachine *pop() {
      TuringMachine* tm = NULL;

      if (!local_queue_.empty()) {
        tm = local_queue_.top();
        local_queue_.pop();
      } else {
      }

      return tm;
    }

  private:
    int master_proc_num_;

    std::stack<TuringMachine*> local_queue_;

    int max_queue_size_;
    int target_queue_size_;
};


/*
class MasterWorkQueue {
  public:

};
*/

}  // namespace lazy_beaver


int main(int argc, char* argv[]) {
  if (argc < 4) {
    std::cerr << "Usage: lazy_beaver_enum num_states num_symbols max_steps [outfile]" << std::endl;
    return 1;
  } else {
    const int num_states = std::stoi(argv[1]);
    const int num_symbols = std::stoi(argv[2]);
    const long max_steps = std::stol(argv[3]);

    std::ofstream* outstream = nullptr;
    if (argc >= 5) {
      const std::string outfilename(argv[4]);
      outstream = new std::ofstream(outfilename, std::ios::out);
    }

    long ret = lazy_beaver::Enumerate(num_states, num_symbols, max_steps, outstream);
    if (outstream != nullptr) {
      outstream->close();
    }

    if (ret < 0) {
      // Error/inconclusive
      return 1;
    } else {
      // Success
      return 0;
    }
  }
}
