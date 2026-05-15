# Proposal

## General considerations

- Functions (even _def_) can be defined arbitrarily deep inside conditional code -- that code needs to execute
  to even determine the definition of the function. This seems incompatible with the idea of statically
  determining the "calls" relation. On the other hand, if a function is "definitely assigned" then all its
  "candidate definitions" are statically known so we could over-approximate its "calls" set (by unioning).

## Proposal 1: SCC picture

- All _def_ functions and other vars in a given function scope are known up front (= hoisting).
- Identify strongly conected components (SCCs) in graph G of static "calls" relation (defs only -- vars that
  happen to evaluate to lambdas won't support mutual recursion).
- Forms the condensation G^SCC of that graph (quotient w.r.t. "membership of same SCC") -- necessarily
  acyclic.
- Each vertex of G^SCC forms a single unit of simultaneous function definition. Pick a topological ordering,
  initialise in that order.
- [Perhaps] At runtime, when initialising an SCC: execute statements sequentially; returns set of definitions
  (for functions, not yet closures!); then build the closures simultaneously in the context of the other
  variables.

### Problems with this idea

- Variable assignments (e.g. definitions of constants) may be interleaved arbitrarily between function
  definitions.
- The sequential semantics of all these executable stuff needs to be preserved even though the topological
  sort of G^SCC effectively wants to reorder function definitions.

### Examples

```python
# ------------------
# {h, i} is an SCC
def h ():
   i()

debug = false # code "inside" an SCC

def i ():
   if debug:
      return h()
   else:
      return f() # directed edge from {h, i} to {f, g}
# ------------------

# code can also go here (between SCCs)

# ------------------
# {f, g} is an SCC
def f ():
   g()

debug2 = debug

def g ():
   if debug2:
      return f()
# ------------------
```

Challenge: `g` uses `debug`, but {f, g} needs to be defined before {h, i}.

Options:
- Prohibit "forward ref" from {h, i} to {f, g}; in other words require the _user_ to provide the topological
  sort of G^SCC. Downside: because changing the usage graph changes the SCC, dropping a "within-SCC" edge into
  an illegal forward reference between SCCs. There would be a (maybe) surprising antitonicity where _removing_
  usage would _further constrain_ sequential arrangement of definitions. For example the forward-ref (h, i) in
  G is _permitted_ because there is also an edge (i, h), so they form a SCC; but removing (i, h) would make
  the forward-ref illegal because {h, i} is no longer an SCC but rather {h} and {i} are their own SCCs with
  an edge ({h}, {i}) between them (illegal if we prohibit SCC forward-refs).
- Permit forward ref from {h, i} to {f, g}, but execute the two SCC's code in topological order. Then we have
  the problem that the execution order differs from the lexical order in the code. In the example, the
  assignment to `debug2` would need to execute before the assignment to `debug`. We could rule _that_ out, but
  that has its own element of surprise; the above would be illegal as long as there was a call from {h, i} to
  {f, g}. And if we added a print effect into the mix, then the reordering really wouldn't be possible without
  changing the observed behaviour.

## Proposal 2: one big mutual block

This goes "maximal" rather than minimal and says that _all_ function definitions in a given scope are mutually
recursive. I think this would need a delineation between statements that occur before or within the block
(that would be executed before closure creation) and those that occur after. Otherwise there'd be no way to
define a module with a statement that called one of the functions in the module (e.g. `main`).

## Proposal 3: mutual blocks delimited by non-function statements

Middle ground where mutual blocks are maximal _contiguous_ blocks of function definitions. All statements
_within_ the block are executed before closure creation, as Proposal 2, so that any additional variable
definitions are in scope for the closures. So really this is just a more granular version of Proposal 2. On
the other hand it's less granular than Proposal 1, which has the advantage that breaking a usage cycle within
a contiguous block _doesn't_ break forward-references within the block, which could be surprising and tedious.
