# Mutual recursion

## Working assumption: contiguous mutual blocks

A *mutual block* is a maximal contiguous sequence of `def` statements at a given scope. Any non-`def`
statement separates blocks. Within a block, all names are bound simultaneously and may forward-reference
each other; across blocks, ordinary sequential scoping applies.

The block boundary is purely syntactic. As a static-semantic constraint, the names bound in a single block
must be unique.

At runtime: each statement block executes sequentially, then the following mutual block is processed
simultaneously (closures built with all names in the block in scope), then the next statement block, and so
on.

Examples:

- [`mutual.py`](test/well-formed/functions/mutual.py): canonical even/odd, contiguous, called after the block.
  ```python
  def even(n):
      if n == 0:
          return True
      return odd(n - 1)

  def odd(n):
      if n == 0:
          return False
      return even(n - 1)

  print(even(10))
  print(odd(10))
  ```
- [`mutual_split_by_call_late_binding.py`](test/ill-formed/semantic/mutual_split_by_call_late_binding.py),
  [`mutual_split_by_call_nameerror.py`](test/ill-formed/semantic/mutual_split_by_call_nameerror.py),
  [`mutual_split_by_assign.py`](test/ill-formed/semantic/mutual_split_by_assign.py): rejected because a
  non-`def` statement splits the would-be block.
- [`duplicate_def_in_block.py`](test/ill-formed/semantic/duplicate_def_in_block.py): rejected because the
  same name is bound twice in one block.
- [`mutual_after_rebind.py`](test/well-formed/functions/mutual_after_rebind.py): a name bound in one block
  may be rebound by a later block, provided nothing in between captured it.

## Branch-local definitions

Function variables are scoped at the enclosing function/module level (Python hoists definitions to the
front), but assignment via `def` happens only when the statement executes. So `def`s in different branches
of a conditional are independent contiguous blocks within their branch:

```python
if b:
   def f():
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

A `def` that appears only in some branches binds a name that is not definitely assigned after the
conditional, even though it is in scope. See
[`mutual_def_block_local.py`](test/ill-formed/semantic/mutual_def_block_local.py) for the rejected case
where such a name is used outside the branch, and
[`mutual_def_in_branch.py`](test/well-formed/functions/mutual_def_in_branch.py) for the well-formed case
where both branches bind both names.

## Reassignment of a captured name

The general rule against reassigning a captured variable still applies. So:

```python
def g ():
   pass

if b:
   def f():
      g()

   def g():    # illegal: attempt to reassign captured g
      f()
```

is rejected because `def g` inside the branch reassigns `g`, which has been captured by `def f`. See
[`shadow_captured_mutual.py`](test/ill-formed/semantic/shadow_captured_mutual.py) for the same shape
without the conditional.

## Considered alternatives

### SCC picture

Identify strongly connected components (SCCs) in the static "calls" relation among `def`s; each SCC forms
one unit of simultaneous definition; pick a topological ordering. Problems:

- Variable assignments may be interleaved arbitrarily between function definitions.
- The sequential semantics needs to be preserved even though the topological sort wants to reorder
  function definitions.
- Removing a usage edge (within an SCC) can break a previously-legal program by demoting an internal reference
  into a forward reference between two SCCs (an "antitonicity" surprise).

### One big mutual block

All `def`s in a given scope are (permitted to be) mutually recursive. Requires distinguishing statements that
come *within* the block (run before closure creation, available to all functions) from those *after* (e.g. a
`main` call). Loses the simple "non-`def` statement = block boundary" definition we get from contiguous
blocks.

## Why non-`def` statements terminate blocks

Consider what would have to happen if a mutual block spanned a non-`def` statement:

```python
def g():
   f(False)

if b1:
  def f(b2):
     if b2:
        g()     # mutual with g
else:
  def f(b2):
     pass       # not mutual, but conservatively assume {f, g} form a SCC
```

The static call graph puts `f` and `g` in one SCC, so a closure for `g` would need `f` already bound. But
`f`'s body isn't statically determined: it depends on which branch of the conditional runs. To build the
closure we would need to evaluate the conditional first; evaluating may involve calling `f`. There is no
clear way to construct the closures.

Restricting mutual blocks to contiguous `def`s sidesteps this: the conditional is a statement that
terminates whatever block precedes it, so `g` and `f` end up in separate blocks and the SCC question never
arises. The forward reference from `g` to `f` is then rejected by the usual definite-assignment rule.
