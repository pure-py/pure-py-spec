from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class DuplicateFieldName:
    name: str
    cls: str
    def message(self) -> str:
        return f"duplicate field name '{self.name}' in class '{self.cls}'"


@dataclass(frozen=True)
class UnknownBaseClass:
    base: str
    def message(self) -> str:
        return f"base class '{self.base}' is not declared in this module"


@dataclass(frozen=True)
class InheritedFieldClash:
    field: str
    base: str
    def message(self) -> str:
        return f"field '{self.field}' clashes with inherited field from '{self.base}'"


@dataclass(frozen=True)
class UnassignedVariable:
    name: str
    def message(self) -> str:
        return f"'{self.name}' is not definitely assigned"


@dataclass(frozen=True)
class CapturedReassignment:
    name: str
    def message(self) -> str:
        return f"'{self.name}' captured by previous statement, reassigned here"


@dataclass(frozen=True)
class SelfCaptureAssignment:
    name: str
    def message(self) -> str:
        return f"'{self.name}' captured by right-hand side"


@dataclass(frozen=True)
class UnreachableStatement:
    def message(self) -> str:
        return "unreachable statement"


@dataclass(frozen=True)
class ConstructorArityMismatch:
    cls: str
    expected: int
    got: int
    def message(self) -> str:
        return f"constructor for '{self.cls}' expects {self.expected} arguments, got {self.got}"


@dataclass(frozen=True)
class UnknownConstructorKeyword:
    cls: str
    expected_fields: tuple[str, ...]
    def message(self) -> str:
        return f"constructor keywords for '{self.cls}' must be {', '.join(self.expected_fields)}"


@dataclass(frozen=True)
class PatternArityMismatch:
    cls: str
    expected: int
    got: int
    def message(self) -> str:
        return f"pattern for '{self.cls}' expects {self.expected} sub-patterns, got {self.got}"


@dataclass(frozen=True)
class UnknownClassInPattern:
    cls: str
    def message(self) -> str:
        return f"'{self.cls}' is not a declared class"


@dataclass(frozen=True)
class UnknownFieldInPattern:
    cls: str
    expected_fields: tuple[str, ...]
    def message(self) -> str:
        return f"pattern keywords for '{self.cls}' must be {', '.join(self.expected_fields)}"


@dataclass(frozen=True)
class DuplicatePatternKeyword:
    cls: str
    def message(self) -> str:
        return f"duplicate keyword in pattern for '{self.cls}'"


@dataclass(frozen=True)
class NonlinearPattern:
    index: int
    def message(self) -> str:
        return f"repeated variable in pattern {self.index}"


@dataclass(frozen=True)
class UnreachableCase:
    index: int
    subsumed_by: int
    def message(self) -> str:
        return f"case {self.index} unreachable: subsumed by case {self.subsumed_by}"


@dataclass(frozen=True)
class DuplicateMutualName:
    name: str
    def message(self) -> str:
        return f"duplicate name '{self.name}' in mutual region"


@dataclass(frozen=True)
class NonTopLevelImport:
    def message(self) -> str:
        return "import only allowed at module top level"


@dataclass(frozen=True)
class ImportAfterStatement:
    def message(self) -> str:
        return "imports must precede all other statements"


@dataclass(frozen=True)
class SubmoduleNameClash:
    name: str
    submodule: str
    def message(self) -> str:
        return f"binding '{self.name}' clashes with submodule '{self.submodule}'"


@dataclass(frozen=True)
class SubmoduleNotImported:
    q: str
    def message(self) -> str:
        return f"submodule '{self.q}' is not imported"


@dataclass(frozen=True)
class UnassignedMember:
    x: str
    q: str
    def message(self) -> str:
        return f"member '{self.x}' of module '{self.q}' is not definitely assigned"


@dataclass(frozen=True)
class NonTopLevelClass:
    def message(self) -> str:
        return "class definition only allowed at module top level"


@dataclass(frozen=True)
class TopLevelReturn:
    def message(self) -> str:
        return "top-level return not allowed (module body must not return)"


@dataclass(frozen=True)
class EmptyFromImport:
    def message(self) -> str:
        return "empty name list"


@dataclass(frozen=True)
class UnknownModule:
    q: str
    def message(self) -> str:
        return f"unknown module {self.q!r}"


@dataclass(frozen=True)
class UnknownMember:
    x: str
    q: str
    def message(self) -> str:
        return f"module {self.q!r} has no member {self.x!r}"


@dataclass(frozen=True)
class ModuleAsValue:
    name: str
    def message(self) -> str:
        return f"'{self.name}' refers to a module; modules are not first-class values"


Reason = Union[
    DuplicateFieldName, UnknownBaseClass, InheritedFieldClash,
    UnassignedVariable, CapturedReassignment, SelfCaptureAssignment,
    UnreachableStatement, ConstructorArityMismatch, PatternArityMismatch,
    UnknownClassInPattern, UnknownFieldInPattern, DuplicatePatternKeyword,
    UnknownModule, UnknownMember, ModuleAsValue,
    UnknownConstructorKeyword,
    NonlinearPattern, UnreachableCase, DuplicateMutualName,
    NonTopLevelImport, NonTopLevelClass, TopLevelReturn, EmptyFromImport,
    ImportAfterStatement, SubmoduleNameClash, SubmoduleNotImported,
    UnassignedMember,
]
