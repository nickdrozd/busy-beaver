typedef struct
{
  int w;
  int d;
  int s;
} TRANSITION;

typedef struct
{
  TRANSITION* t;
} STATE;

typedef struct
{
  int num_states;
  int num_symbols;

  STATE* machine;

  int* tape;
  int  tape_length;

  int symbol;

  int                total_symbols;
  unsigned long long total_steps;

  int position;
  int max_left;
  int max_right;

  int state;

  int new_symbol;
  int new_delta;
  int new_state;
} TM;