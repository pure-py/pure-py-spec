# rule: dict-comp
from typing import Callable

fs: dict[str, Callable[[], int]] = {k: (lambda: len(k)) for k in ["a"]}
print(fs["a"]())
