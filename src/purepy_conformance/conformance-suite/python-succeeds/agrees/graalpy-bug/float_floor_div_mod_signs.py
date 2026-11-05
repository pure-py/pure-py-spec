# rule: eval-binop
# bug: https://github.com/oracle/graalpython/issues/1274
print(1.0 // 0.1)
print(-1e-100 % 1e100)
print(-0.0 % 1.0)
print(0.0 % -1.0)
print(-1.0 // 1e400)
print(-1.0 % 1e400)
