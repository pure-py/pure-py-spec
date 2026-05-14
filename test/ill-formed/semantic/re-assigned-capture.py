y = 9
def foo():
  x = y       # points to the definition on line 1
  def bar():
    return x
  return bar()
y = 2         # reassignment of a variable that has been captured, but changes the semantics
print(foo())  # Python prints 2
