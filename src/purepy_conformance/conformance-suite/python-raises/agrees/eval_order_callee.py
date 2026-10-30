# rule: eval-call-fail
from typing import Callable


def h() -> Callable[[int], int]:
    assert False


print(h()(1 // 0))
