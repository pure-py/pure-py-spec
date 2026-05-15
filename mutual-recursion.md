# Proposal

## General considerations

### Conditional `def` (branch-local functions)

Functions (even _def_) can be defined arbitrarily deep inside conditional code -- that code needs to execute
to even determine the definition of the function. This seems somewhat incompatible with the idea of statically
determining the "calls" relation; on the other hand if a function is "definitely assigned" then all its
"candidate definitions" are statically known, so we could over-approximate its "calls" set (by unioning). So
let's put that issue to one side.

A residual issue is resolving how these conditional defs at runtime, in the presence of mutual recursion. I
think this question is independent of the granularity of mutual blocks. Consider the following:

```python
def g():
   f(false)

if b1:
  def f(b2):
     if b2:
        g()     # mutual with g
else:
  def f(b2):
     pass       # not mutual, but let's over-approximate and assume {f, g} form a SCC
```

Currently, we build closures when we evaluate a `def`. With mutual recursion, we need to build each closure
for a given function with _at least_ the SCC containing that function, plus any other prior bindings used by
the SCC as a whole. (Coarser granularities are possible; see Proposals 1-3 below.) So here, suitably
approximated, {f, g} is an SCC and we need to build the closures for f and g simultaneously, including the
definitions of f and g into the closures. But here the conditional code surrounding the definition of `f` gets
in the way. There's a cycle: to know what the static body of 'f' is (needed to build the closures), I need to
evaluate the statement; but evaluating the statement may involve calling 'f' (after all, being able to call
'f' locally is the main reason for wanting branch-local definitions). To break the cycle, we'd need to bundle
all that top-level conditional code as part of the definition of `f` that goes into the closure, but that
sounds intense and/or problematic.

[Aside: from a _typing_ point of view, implementors that want to layer non-trivial type systems on top of
PurePy would have to contend with multiple definitions of the same function -- so perhaps supporting this
feature is misguided. But note that we already have that problem: a non-def variable might have function type,
and might be assigned different functional in different branches.]

Just ruling them out entirely is one option, but would mean we can no longer define branch-local functions.

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
recursive. I think this would need provision for:
- allowing other statements _within_ the block (that would need to be executed _before_ closure creation,
  making them available to all functions), to support important idioms e.g. defining constants which are used
  by functions
- statements coming _after_ the block, otherwise there would be no way to define a module with a statement
  that called one of the functions in the module (e.g. `main`).

## Proposal 3: mutual blocks delimited by non-function statements

Middle ground where mutual blocks are maximal _contiguous_ blocks of function definitions. By definition there
are no statements _within_ a mutual block; the presence of statements is exactly what determines the block
structure. (Perhaps Proposal 2 could be understood as a rewriting into a degenerate Proposal 3 format, pulling
all statements prior to the last function definition to the beginning of the module.) The advantage over
Proposal 1 is that breaking a usage cycle within a contiguous block _doesn't_ break forward-references within
the block, which could be surprising and tedious.

So the runtime picture is: the first statement block is executed, establishing additional assignments as
normal; then the first mutual block is processed simultaneously, establishing additional function assignments;
then repeat until the final statement block.

A key consideration is what happens with branch-local statements. I think they can be processed in exactly the
same way. So for example, the following would be permitted (ignoring non-termination for the purposes of this
example!):

```python
if b:
   def f ():
      g()

   def g():
      f()

   # f and g defined mutually; both usable here
else:
   def f():
      pass

   def g():
      pass

   # f and g defined independently; both usable here
# both usable here too
```

whereas:

```python
if b:
   def f():
      g()         # illegal -- g not part of f's contiguous (implicit mutual) block

   if b2:
      def g():
         pass
```

What about _redefining_ existing functions, i.e. if a branch-local `f` tries to forward-reference a
branch-local `g`, when `g` is already definitely assigned? I think this is covered by the prohibition of
reassignment of captured variables:

```python
def g ():
   pass

if b:
   def f():
      g()

   def g():    # illegal; attempt to reassign captured variable
      f()
```
