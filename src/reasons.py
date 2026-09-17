import ast
from dataclasses import dataclass

from type_syntax import QualifiedName, Type, Var, render


@dataclass(frozen=True)
class DuplicateField:
    x: Var
    c: Var

    def message(self) -> str:
        return f"duplicate field '{self.x}' in class '{self.c}'"


@dataclass(frozen=True)
class ClassRebound:
    c: Var

    def message(self) -> str:
        return f"'{self.c}' is bound to a class and cannot be rebound at top level"


@dataclass(frozen=True)
class UndefinedVariable:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' is not defined"


@dataclass(frozen=True)
class UnassignedVariable:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' is not definitely assigned"


@dataclass(frozen=True)
class CapturedReassignment:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' captured by previous statement, reassigned here"


@dataclass(frozen=True)
class SelfCaptureAssignment:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' captured by right-hand side"


@dataclass(frozen=True)
class CapturedGeneratorVariable:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' bound by generator, captured by lambda"


@dataclass(frozen=True)
class UnreachableStatement:
    def message(self) -> str:
        return "unreachable statement"


@dataclass(frozen=True)
class ConstructorArityMismatch:
    c: Var
    expected: int
    got: int

    def message(self) -> str:
        return f"constructor for '{self.c}' expects {self.expected} arguments, got {self.got}"


@dataclass(frozen=True)
class UnknownConstructorKeyword:
    c: Var
    xs: tuple[Var, ...]

    def message(self) -> str:
        return f"constructor keywords for '{self.c}' must be {', '.join(self.xs)}"


@dataclass(frozen=True)
class PatternArityMismatch:
    c: Var
    expected: int
    got: int

    def message(self) -> str:
        return f"pattern for '{self.c}' expects {self.expected} sub-patterns, got {self.got}"


@dataclass(frozen=True)
class NotPredefinedName:
    x: Var

    def message(self) -> str:
        return f"'{self.x}' is not bound as a predefined name"


@dataclass(frozen=True)
class NotClass:
    q: QualifiedName

    def message(self) -> str:
        return f"'{self.q}' is not a declared class"


@dataclass(frozen=True)
class UnknownFieldInPattern:
    c: Var
    xs: tuple[Var, ...]

    def message(self) -> str:
        return f"pattern keywords for '{self.c}' must be {', '.join(self.xs)}"


@dataclass(frozen=True)
class DuplicatePatternKeyword:
    c: Var

    def message(self) -> str:
        return f"duplicate keyword in pattern for '{self.c}'"


@dataclass(frozen=True)
class DuplicateDictKey:
    w: str

    def message(self) -> str:
        return f"duplicate key '{self.w}' in dict pattern"


@dataclass(frozen=True)
class NonlinearPattern:
    x: Var

    def message(self) -> str:
        return f"repeated variable '{self.x}' in pattern"


@dataclass(frozen=True)
class DuplicateMutualName:
    x: Var

    def message(self) -> str:
        return f"duplicate name '{self.x}' in mutual region"


@dataclass(frozen=True)
class DuplicateMember:
    x: Var
    q: QualifiedName

    def message(self) -> str:
        return (
            f"duplicate member of module '{self.q}': "
            f"it defines '{self.x}' and also has submodule '{self.q}.{self.x}'"
        )


@dataclass(frozen=True)
class SubmoduleNotImported:
    q: QualifiedName

    def message(self) -> str:
        return f"submodule '{self.q}' is not imported"


@dataclass(frozen=True)
class UnassignedMember:
    x: Var
    q: QualifiedName

    def message(self) -> str:
        return f"member '{self.x}' of module '{self.q}' is not definitely assigned"


@dataclass(frozen=True)
class TopLevelReturn:
    def message(self) -> str:
        return "top-level return not allowed (module body must not return)"


@dataclass(frozen=True)
class UnknownModule:
    q: QualifiedName

    def message(self) -> str:
        return f"unknown module '{self.q}'"


@dataclass(frozen=True)
class UnknownMember:
    x: Var
    q: QualifiedName

    def message(self) -> str:
        return f"module '{self.q}' has no member '{self.x}'"


@dataclass(frozen=True)
class ModuleAsValue:
    q: QualifiedName

    def message(self) -> str:
        return f"'{self.q}' refers to a module; modules are not first-class values"


@dataclass(frozen=True)
class ImportOfContainedModule:
    q: QualifiedName
    q_: QualifiedName
    from_import: str

    def message(self) -> str:
        return (
            f"'{self.q}' is contained in importing module '{self.q_}'; "
            f"plain import not allowed, write '{self.from_import}'"
        )


@dataclass(frozen=True)
class PredefinedNameAsValue:
    q: QualifiedName

    def message(self) -> str:
        return f"'{self.q}' is usable only in annotations or as a decorator"


@dataclass(frozen=True)
class ClassAsValue:
    q: QualifiedName

    def message(self) -> str:
        return f"'{self.q}' refers to a class; classes are not first-class values"


@dataclass(frozen=True)
class NoBinaryOverload:
    op: str
    sigma: Type
    sigma_: Type

    def message(self) -> str:
        return f"no overload of '{self.op}' at operand types {render(self.sigma)} and {render(self.sigma_)}"


@dataclass(frozen=True)
class NoUnaryOverload:
    op: str
    sigma: Type

    def message(self) -> str:
        return f"no overload of '{self.op}' at operand type {render(self.sigma)}"


@dataclass(frozen=True)
class NotCallable:
    tau: Type

    def message(self) -> str:
        return f"values of type {render(self.tau)} cannot be called"


@dataclass(frozen=True)
class CallArityMismatch:
    expected: int
    given: int

    def message(self) -> str:
        return f"call expects {self.expected} arguments, given {self.given}"


@dataclass(frozen=True)
class TypeMismatch:
    expected: Type
    actual: Type

    def message(self) -> str:
        return f"expected type {render(self.expected)}, given {render(self.actual)}"


@dataclass(frozen=True)
class LambdaTypeMismatch:
    expected: Type
    arity: int | None

    def message(self) -> str:
        given = (
            "a lambda"
            if self.arity is None
            else f"a lambda of {self.arity} parameter{'' if self.arity == 1 else 's'}"
        )
        return f"expected type {render(self.expected)}, given {given}"


@dataclass(frozen=True)
class NotSubscriptable:
    tau: Type

    def message(self) -> str:
        return f"values of type {render(self.tau)} cannot be subscripted"


@dataclass(frozen=True)
class TupleIndexOutOfRange:
    index: int
    length: int

    def message(self) -> str:
        return f"index {self.index} out of range for tuple of length {self.length}"


@dataclass(frozen=True)
class UnreachableCase:
    index: int

    def message(self) -> str:
        return f"case {self.index} is unreachable"


@dataclass(frozen=True)
class SequenceKindMismatch:
    pattern: str
    tau: Type

    def message(self) -> str:
        return (
            f"{self.pattern} against values of type {render(self.tau)}; list patterns "
            "match only lists and tuple patterns only tuples"
        )


@dataclass(frozen=True)
class NotIterable:
    tau: Type

    def message(self) -> str:
        return f"values of type {render(self.tau)} cannot be iterated"


@dataclass(frozen=True)
class UnknownField:
    c: Var
    x: Var

    def message(self) -> str:
        return f"class '{self.c}' has no field '{self.x}'"


@dataclass(frozen=True)
class NotSynthesised:
    def message(self) -> str:
        return "cannot infer type of this expression; annotate the assignment"


@dataclass(frozen=True)
class NoAttributes:
    tau: Type

    def message(self) -> str:
        return f"values of type {render(self.tau)} have no attributes"


@dataclass(frozen=True)
class MissingReturn:
    x: Var
    tau: Type

    def message(self) -> str:
        return f"'{self.x}' declares result type {render(self.tau)} but does not always return"


type Reason = (
    DuplicateField
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
    | DuplicateMember
    | SubmoduleNotImported
    | ImportOfContainedModule
    | UnassignedMember
    | NoBinaryOverload
    | NoUnaryOverload
    | NotCallable
    | CallArityMismatch
    | TypeMismatch
    | LambdaTypeMismatch
    | NotSubscriptable
    | TupleIndexOutOfRange
    | MissingReturn
    | NotIterable
    | SequenceKindMismatch
    | UnreachableCase
    | NotSynthesised
    | NoAttributes
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
