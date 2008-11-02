#include "Define.h"
#include "TTable.h"
#include "Turing_Machine.h"
#include "Simple_Turing_Machine.h"
#include "Block_Finder.h"
#include "Macro_Turing_Machine.h"
#include "Backsymbol_Turing_Machine.h"
#include "Chain_Simulator.h"

void usage()
{
  fprintf(stderr,"Usage: QuickSim [-b] [-m] [-p] [-r] [-br] [-bs block_size] [TMfile]\n");
}

main(int argc, char** argv)
{
  const char* filename = NULL;
  FILE* file;

  TTable ttable;

  int block_size = 0;

  bool back      = true;
  bool macro     = true;
  bool prover    = true;
  bool recursive = false;
  bool verbose   = true;

  int argIndex;

  for (argIndex = 1; argIndex < argc; argIndex++)
  {
    if (strcmp(argv[argIndex],"-b") == 0)
    {
      back = false;
      continue;
    }

    if (strcmp(argv[argIndex],"-m") == 0)
    {
      macro = false;
      continue;
    }

    if (strcmp(argv[argIndex],"-p") == 0)
    {
      prover = false;
      continue;
    }

    if (strcmp(argv[argIndex],"-r") == 0)
    {
      recursive = true;
      continue;
    }

    if (strcmp(argv[argIndex],"-br") == 0)
    {
      verbose = false;
      continue;
    }

    if (strcmp(argv[argIndex],"-bs") == 0)
    {
      argIndex++;
      block_size = atoi(argv[argIndex]);
      continue;
    }

    if (strncmp(argv[argIndex],"-",1) == 0)
    {
      fprintf(stderr,"Unknown option: '%s'\n",argv[argIndex]);
      usage();
      exit(1);
    }

    if (filename == NULL)
    {
      filename = argv[argIndex];
    }
    else
    {
      fprintf(stderr,"Multiple files specified: '%s' and '%s'\n",filename,argv[argIndex]);
      usage();
      exit(1);
    }
  }

  if (filename == NULL)
  {
    filename = "stdin";
    file = stdin;
  }
  else
  {
    file = fopen(filename,"r");
  }

  if (!ttable.read(file))
  {
    fprintf(stderr,"Unable to parse TM from '%s'\n",filename);
  }

  Turing_Machine* machine = new Simple_Turing_Machine(ttable);

  if (macro)
  {
    if (block_size == 0)
    {
      Block_Finder block_finder(*machine);

      block_size = block_finder.find_block();
    }

    if (block_size > 1)
    {
      machine = new Macro_Turing_Machine(*machine, block_size);
    }
  }

  if (back)
  {
    machine = new Backsymbol_Turing_Machine(*machine);
  }

  Chain_Simulator sim(*machine, recursive, prover);

  Integer extent = 1;
  while (sim.run_state() == Turing_Machine::RUNNING)
  {
    if (verbose)
    {
      sim.print();
    }

    sim.seek(extent);
    extent *= 10;
  }

  sim.print();

  if (sim.run_state() == Turing_Machine::HALT)
  {
    cout << "Turing machine halted:"           << endl;
    cout << "  Steps:   " << sim.num_steps()   << endl;
    cout << "  Nonzero: " << sim.num_nonzero() << endl;
  }
  else
  if (sim.run_state() == Turing_Machine::INFINITE)
  {
    cout << "Turing machine proven infinite:" << endl;
    cout << "  Reason: " << sim.inf_reason()  << endl;
  }
  else
  if (sim.run_state() == Turing_Machine::UNDEFINED)
  {
    cout << "Turing machine reached an undefined transition:" << endl;
    cout << "  State:   " << sim.cur_state()                  << endl;
    cout << "  Symbol:  " << sim.cur_symbol()                 << endl;
    cout << "  Steps:   " << sim.num_steps()                  << endl;
    cout << "  Nonzero: " << sim.num_nonzero()                << endl;
  }
  else
  {
    cout << "Unknown Turing machine state!" << endl;
  }
}
