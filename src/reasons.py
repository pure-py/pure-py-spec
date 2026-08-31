import ast
from dataclasses import dataclass


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
class ClassRebound:
    name: str

    def message(self) -> str:
        return (
            f"'{self.name}' is bound to a class and cannot be rebound at the top level"
        )


@dataclass(frozen=True)
class UndefinedVariable:
    name: str

    def message(self) -> str:
        return f"'{self.name}' is not defined"


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
class CapturedGeneratorVariable:
    name: str

    def message(self) -> str:
        return f"'{self.name}' bound by a generator, captured by a lambda"


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
class UnknownClassInAnnotation:
    cls: str

    def message(self) -> str:
        return f"annotation names '{self.cls}', which is not a declared class"


@dataclass(frozen=True)
class AnnotationNameNotInScope:
    name: str

    def message(self) -> str:
        return f"annotation names '{self.name}', which is not in scope"


@dataclass(frozen=True)
class DecoratorNotInScope:
    name: str

    def message(self) -> str:
        return f"class declaration names '{self.name}', which is not in scope"


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
class DuplicateDictKey:
    key: str

    def message(self) -> str:
        return f"duplicate key '{self.key}' in dict pattern"


@dataclass(frozen=True)
class NonlinearPattern:
    variable: str

    def message(self) -> str:
        return f"repeated variable '{self.variable}' in pattern"


@dataclass(frozen=True)
class DuplicateMutualName:
    name: str

    def message(self) -> str:
        return f"duplicate name '{self.name}' in mutual region"


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
    name: str

    def message(self) -> str:
        return f"'{self.name}' refers to a module; modules are not first-class values"


@dataclass(frozen=True)
class OwnDescendantImport:
    q: str
    q0: str

    def message(self) -> str:
        return f"'{self.q}' is a descendant of the importing module '{self.q0}'; import it with a from-import"


@dataclass(frozen=True)
class PredefinedNameAsValue:
    name: str

    def message(self) -> str:
        return f"'{self.name}' is usable only in an annotation or as a decorator"


@dataclass(frozen=True)
class ClassAsValue:
    name: str

    def message(self) -> str:
        return f"'{self.name}' refers to a class; classes are not first-class values"


@dataclass(frozen=True)
class MissingAnnotation:
    name: str

    def message(self) -> str:
        return f"'{self.name}' must annotate every parameter and its return type"


@dataclass(frozen=True)
class NoBinarySignature:
    op: str
    left: str
    right: str

    def message(self) -> str:
        return f"no signature for '{self.op}' with operands of type {self.left} and {self.right}"


@dataclass(frozen=True)
class NoUnarySignature:
    op: str
    operand: str

    def message(self) -> str:
        return f"no signature for '{self.op}' with operand of type {self.operand}"


@dataclass(frozen=True)
class NotCallable:
    ty: str

    def message(self) -> str:
        return f"call of a value of type {self.ty}, which is not callable"


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
    ty: str

    def message(self) -> str:
        return f"subscript of a value of type {self.ty}, which has no subscript rule"


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
        return f"case {self.index} matches no value the earlier cases leave"


@dataclass(frozen=True)
class PatternTypeMismatch:
    pattern: str
    ty: str

    def message(self) -> str:
        return f"{self.pattern} cannot match a value of type {self.ty}"


@dataclass(frozen=True)
class SequenceKindClash:
    pattern: str
    ty: str

    def message(self) -> str:
        return (
            f"{self.pattern} against a value of type {self.ty}; Python matches "
            "sequence patterns against lists and tuples alike, so PurePy "
            "treats the two kinds as incompatible"
        )


@dataclass(frozen=True)
class NotIterable:
    ty: str

    def message(self) -> str:
        return f"iteration over a value of type {self.ty}, which has no element type"


@dataclass(frozen=True)
class UnknownField:
    cls: str
    field: str

    def message(self) -> str:
        return f"class '{self.cls}' has no field '{self.field}'"


@dataclass(frozen=True)
class NotSynthesised:
    """No synthesis rule gives this expression a type, so it cannot stand where
    a rule demands one."""

    def message(self) -> str:
        return "cannot determine the type of this expression"


@dataclass(frozen=True)
class MissingReturn:
    name: str
    ty: str

    def message(self) -> str:
        return (
            f"'{self.name}' declares result type {self.ty} but does not always return"
        )


Reason = (
    DuplicateFieldName
    | UnknownBaseClass
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
    | UnknownClassInPattern
    | UnknownClassInAnnotation
    | AnnotationNameNotInScope
    | DecoratorNotInScope
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
    | OwnDescendantImport
    | UnassignedMember
    | MissingAnnotation
    | NoBinarySignature
    | NoUnarySignature
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
        self.module: str | None = None
        super().__init__(self.msg)


class IllFormedProgram(IllFormed):
    exit_code = 4

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)
