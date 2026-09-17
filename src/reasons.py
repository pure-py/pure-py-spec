import ast
from dataclasses import dataclass

from type_syntax import QualifiedName


@dataclass(frozen=True)
class DuplicateFieldName:
    x: str
    c: str

    def message(self) -> str:
        return f"duplicate field name '{self.x}' in class '{self.c}'"


@dataclass(frozen=True)
class InheritedFieldClash:
    x: str
    c: str

    def message(self) -> str:
        return f"field '{self.x}' clashes with inherited field from '{self.c}'"


@dataclass(frozen=True)
class ClassRebound:
    c: str

    def message(self) -> str:
        return f"'{self.c}' is bound to a class and cannot be rebound at the top level"


@dataclass(frozen=True)
class UndefinedVariable:
    x: str

    def message(self) -> str:
        return f"'{self.x}' is not defined"


@dataclass(frozen=True)
class UnassignedVariable:
    x: str

    def message(self) -> str:
        return f"'{self.x}' is not definitely assigned"


@dataclass(frozen=True)
class CapturedReassignment:
    x: str

    def message(self) -> str:
        return f"'{self.x}' captured by previous statement, reassigned here"


@dataclass(frozen=True)
class SelfCaptureAssignment:
    x: str

    def message(self) -> str:
        return f"'{self.x}' captured by right-hand side"


@dataclass(frozen=True)
class CapturedGeneratorVariable:
    x: str

    def message(self) -> str:
        return f"'{self.x}' bound by a generator, captured by a lambda"


@dataclass(frozen=True)
class UnreachableStatement:
    def message(self) -> str:
        return "unreachable statement"


@dataclass(frozen=True)
class ConstructorArityMismatch:
    c: str
    expected: int
    got: int

    def message(self) -> str:
        return f"constructor for '{self.c}' expects {self.expected} arguments, got {self.got}"


@dataclass(frozen=True)
class UnknownConstructorKeyword:
    c: str
    xs: tuple[str, ...]

    def message(self) -> str:
        return f"constructor keywords for '{self.c}' must be {', '.join(self.xs)}"


@dataclass(frozen=True)
class PatternArityMismatch:
    c: str
    expected: int
    got: int

    def message(self) -> str:
        return f"pattern for '{self.c}' expects {self.expected} sub-patterns, got {self.got}"


@dataclass(frozen=True)
class NotPredefinedName:
    x: str

    def message(self) -> str:
        return f"'{self.x}' is not bound as a predefined name"


@dataclass(frozen=True)
class NotClass:
    q: str

    def message(self) -> str:
        return f"'{self.q}' is not a declared class"


@dataclass(frozen=True)
class UnknownFieldInPattern:
    c: str
    xs: tuple[str, ...]

    def message(self) -> str:
        return f"pattern keywords for '{self.c}' must be {', '.join(self.xs)}"


@dataclass(frozen=True)
class DuplicatePatternKeyword:
    c: str

    def message(self) -> str:
        return f"duplicate keyword in pattern for '{self.c}'"


@dataclass(frozen=True)
class DuplicateDictKey:
    w: str

    def message(self) -> str:
        return f"duplicate key '{self.w}' in dict pattern"


@dataclass(frozen=True)
class NonlinearPattern:
    x: str

    def message(self) -> str:
        return f"repeated variable '{self.x}' in pattern"


@dataclass(frozen=True)
class DuplicateMutualName:
    x: str

    def message(self) -> str:
        return f"duplicate name '{self.x}' in mutual region"


@dataclass(frozen=True)
class SubmoduleNameClash:
    x: str
    q: str

    def message(self) -> str:
        return f"binding '{self.x}' clashes with submodule '{self.q}'"


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
class TopLevelReturn:
    def message(self) -> str:
        return "top-level return not allowed (module body must not return)"


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
    q: str

    def message(self) -> str:
        return f"'{self.q}' refers to a module; modules are not first-class values"


@dataclass(frozen=True)
class ImportOfContainedModule:
    q: str
    q_: str
    from_import: str

    def message(self) -> str:
        return (
            f"'{self.q}' is contained in the importing module '{self.q_}'; "
            f"a plain import is not allowed, write '{self.from_import}'"
        )


@dataclass(frozen=True)
class PredefinedNameAsValue:
    q: str

    def message(self) -> str:
        return f"'{self.q}' is usable only in an annotation or as a decorator"


@dataclass(frozen=True)
class ClassAsValue:
    q: str

    def message(self) -> str:
        return f"'{self.q}' refers to a class; classes are not first-class values"


@dataclass(frozen=True)
class NoBinaryOverload:
    op: str
    Sigma: str
    Sigma_: str

    def message(self) -> str:
        return f"no overload of '{self.op}' at operand types {self.Sigma} and {self.Sigma_}"


@dataclass(frozen=True)
class NoUnaryOverload:
    op: str
    Sigma: str

    def message(self) -> str:
        return f"no overload of '{self.op}' at operand type {self.Sigma}"


@dataclass(frozen=True)
class NotCallable:
    tau: str

    def message(self) -> str:
        return f"call of a value of type {self.tau}, which is not callable"


@dataclass(frozen=True)
class CallArityMismatch:
    expected: int
    given: int

    def message(self) -> str:
        return f"call expects {self.expected} arguments, given {self.given}"


@dataclass(frozen=True)
class TypeMismatch:
    expected: str
    actual: str

    def message(self) -> str:
        return f"expected type {self.expected}, given {self.actual}"


@dataclass(frozen=True)
class NotSubscriptable:
    tau: str

    def message(self) -> str:
        return f"subscript of a value of type {self.tau}, which has no subscript rule"


@dataclass(frozen=True)
class TupleIndexOutOfRange:
    index: int
    length: int

    def message(self) -> str:
        return f"index {self.index} out of range for a tuple of length {self.length}"


@dataclass(frozen=True)
class CaseMatchesNothing:
    index: int

    def message(self) -> str:
        return f"case {self.index} matches no value left by the earlier cases"


@dataclass(frozen=True)
class PatternTypeMismatch:
    pattern: str
    tau: str

    def message(self) -> str:
        return f"{self.pattern} cannot match a value of type {self.tau}"


@dataclass(frozen=True)
class SequenceKindClash:
    pattern: str
    tau: str

    def message(self) -> str:
        return (
            f"{self.pattern} against a value of type {self.tau}; Python matches "
            "sequence patterns against lists and tuples alike, so PurePy "
            "treats the two kinds as incompatible"
        )


@dataclass(frozen=True)
class NotIterable:
    tau: str

    def message(self) -> str:
        return f"iteration over a value of type {self.tau}, which has no element type"


@dataclass(frozen=True)
class UnknownField:
    c: str
    x: str

    def message(self) -> str:
        return f"class '{self.c}' has no field '{self.x}'"


@dataclass(frozen=True)
class NotSynthesised:
    def message(self) -> str:
        return "cannot determine the type of this expression"


@dataclass(frozen=True)
class MissingReturn:
    x: str
    tau: str

    def message(self) -> str:
        return f"'{self.x}' declares result type {self.tau} but does not always return"


type Reason = (
    DuplicateFieldName
    | InheritedFieldClash
    | ClassRebound
    | UnassignedVariable
    | UndefinedVariable
    | CapturedReassignment
    | SelfCaptureAssignment
    | CapturedGeneratorVariable
    | UnreachableStatement
    | ConstructorArityMismatch
    | PatternArityMismatch
    | NotClass
    | NotPredefinedName
    | UnknownFieldInPattern
    | DuplicatePatternKeyword
    | UnknownModule
    | UnknownMember
    | ModuleAsValue
    | ClassAsValue
    | PredefinedNameAsValue
    | UnknownConstructorKeyword
    | DuplicateDictKey
    | NonlinearPattern
    | DuplicateMutualName
    | TopLevelReturn
    | SubmoduleNameClash
    | SubmoduleNotImported
    | ImportOfContainedModule
    | UnassignedMember
    | NoBinaryOverload
    | NoUnaryOverload
    | NotCallable
    | CallArityMismatch
    | TypeMismatch
    | NotSubscriptable
    | TupleIndexOutOfRange
    | MissingReturn
    | NotIterable
    | PatternTypeMismatch
    | SequenceKindClash
    | CaseMatchesNothing
    | NotSynthesised
    | UnknownField
)


class IllFormed(Exception):
    exit_code: int
    msg: str


class IllFormedModule(IllFormed):
    exit_code = 3

    def __init__(self, node: ast.AST, reason: Reason):
        self.line: int | None = getattr(node, "lineno", None)
        self.col: int | None = getattr(node, "col_offset", None)
        self.msg = reason.message()
        self.module: QualifiedName | None = None
        super().__init__(self.msg)


class IllFormedProgram(IllFormed):
    exit_code = 4

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)
