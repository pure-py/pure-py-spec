# rule: call-lambda
from typing import Callable

fs: list[Callable[[int], int]] = [(lambda n: (lambda x: x + n))(i) for i in [1, 2]]
print(fs[0](10))
