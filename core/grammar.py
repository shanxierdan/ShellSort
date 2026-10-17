"""Typed grammar and immutable partial-program search state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .dsl import Expr
from .generators import EnumerativeGenerator, GapGenerator, RecursiveGenerator


class ValueType(str, Enum):
    REAL = "real"
    BOOL = "bool"


@dataclass(frozen=True)
class Production:
    name: str
    output: ValueType | None
    children: tuple[ValueType, ...] = ()
    op: str | None = None
    value: float | str | None = None
    contexts: frozenset[str] = frozenset({"init", "next", "element", "keep"})


def _productions() -> tuple[Production, ...]:
    items = [
        Production("template_recursive", None),
        Production("template_enumerative", None),
        Production("bound_2", None),
        Production("bound_4", None),
        Production("bound_8", None),
        Production("bound_16", None),
    ]
    for value in (0.5, 1.0, 2.0, 3.0, 4.0):
        items.append(Production(f"const_{value:g}", ValueType.REAL, op="const", value=value))
    items.extend(
        (
            Production("var_n", ValueType.REAL, op="var", value="n"),
            Production("var_h", ValueType.REAL, op="var", value="h", contexts=frozenset({"next"})),
            Production("var_i", ValueType.REAL, op="var", value="i", contexts=frozenset({"next"})),
            Production("var_a", ValueType.REAL, op="var", value="a", contexts=frozenset({"element"})),
            Production("var_b", ValueType.REAL, op="var", value="b", contexts=frozenset({"element"})),
            Production("var_a_keep", ValueType.REAL, op="var", value="a", contexts=frozenset({"keep"})),
            Production("var_b_keep", ValueType.REAL, op="var", value="b", contexts=frozenset({"keep"})),
            Production("var_g", ValueType.REAL, op="var", value="g", contexts=frozenset({"keep"})),
        )
    )
    for op in ("floor", "ceil", "sqrt", "log"):
        items.append(Production(op, ValueType.REAL, (ValueType.REAL,), op=op))
    for op in ("add", "sub", "mul", "div", "min", "max", "pow"):
        items.append(Production(op, ValueType.REAL, (ValueType.REAL, ValueType.REAL), op=op))
    for op in ("lt", "le", "eq"):
        items.append(Production(op, ValueType.BOOL, (ValueType.REAL, ValueType.REAL), op=op, contexts=frozenset({"keep"})))
    for op in ("and", "or"):
        items.append(Production(op, ValueType.BOOL, (ValueType.BOOL, ValueType.BOOL), op=op, contexts=frozenset({"keep"})))
    items.append(Production("not", ValueType.BOOL, (ValueType.BOOL,), op="not", contexts=frozenset({"keep"})))
    return tuple(items)


PRODUCTIONS = _productions()
ACTION_NAMES = tuple(item.name for item in PRODUCTIONS)
ACTION_BY_NAME = {item.name: index for index, item in enumerate(PRODUCTIONS)}
BOUNDS = {"bound_2": 2, "bound_4": 4, "bound_8": 8, "bound_16": 16}


def parse_prefix(actions: tuple[int, ...]) -> Expr:
    def parse(cursor: int) -> tuple[Expr, int]:
        production = PRODUCTIONS[actions[cursor]]
        cursor += 1
        children: list[Expr] = []
        for _ in production.children:
            child, cursor = parse(cursor)
            children.append(child)
        if production.op == "const":
            return Expr.constant(float(production.value)), cursor
        if production.op == "var":
            return Expr.variable(str(production.value)), cursor
        if production.op is None:
            raise ValueError("non-expression action in expression prefix")
        return Expr(production.op, tuple(children)), cursor

    expression, end = parse(0)
    if end != len(actions):
        raise ValueError("unused actions after expression")
    return expression


@dataclass(frozen=True)
class SearchState:
    max_nodes: int = 20
    template: str | None = None
    bound_a: int | None = None
    bound_b: int | None = None
    field_index: int = 0
    fields: tuple[tuple[int, ...], ...] = ()
    holes: tuple[ValueType, ...] = ()
    history: tuple[int, ...] = ()

    @property
    def terminal(self) -> bool:
        return self.template is not None and self.field_index >= self.field_count and not self.holes

    @property
    def field_count(self) -> int:
        return 2 if self.template in {"recursive", "enumerative"} else 0

    @property
    def context(self) -> str | None:
        if self.template == "recursive":
            return ("init", "next")[self.field_index] if self.field_index < 2 else None
        if self.template == "enumerative" and self.bound_b is not None and self.field_index < 2:
            return ("element", "keep")[self.field_index]
        return None

    @property
    def node_count(self) -> int:
        return sum(len(field) for field in self.fields)

    def legal_actions(self) -> tuple[int, ...]:
        if self.terminal:
            return ()
        if self.template is None:
            legal = []
            if self.max_nodes >= 2:
                legal.append(ACTION_BY_NAME["template_recursive"])
            if self.max_nodes >= 4:
                legal.append(ACTION_BY_NAME["template_enumerative"])
            return tuple(legal)
        if self.template == "enumerative" and self.bound_a is None:
            return tuple(ACTION_BY_NAME[name] for name in BOUNDS)
        if self.template == "enumerative" and self.bound_b is None:
            return tuple(ACTION_BY_NAME[name] for name in BOUNDS)
        if not self.holes:
            return ()
        remaining = self.max_nodes - self.node_count
        context = self.context
        legal: list[int] = []
        for index, production in enumerate(PRODUCTIONS):
            if production.output != self.holes[0] or context not in production.contexts:
                continue
            # Replacing one hole creates len(children) holes. Each needs at least one node.
            pending_types = production.children + self.holes[1:]
            required = sum(3 if value_type == ValueType.BOOL else 1 for value_type in pending_types)
            if self.field_index + 1 < self.field_count:
                future_type = (
                    ValueType.BOOL
                    if self.template == "enumerative" and self.field_index == 0
                    else ValueType.REAL
                )
                required += 3 if future_type == ValueType.BOOL else 1
            if remaining >= 1 + required:
                legal.append(index)
        return tuple(legal)

    def apply(self, action: int) -> "SearchState":
        if action not in self.legal_actions():
            raise ValueError(f"illegal grammar action: {ACTION_NAMES[action]}")
        name = ACTION_NAMES[action]
        history = self.history + (action,)
        if name == "template_recursive":
            return replace(self, template="recursive", fields=((), ()), holes=(ValueType.REAL,), history=history)
        if name == "template_enumerative":
            return replace(self, template="enumerative", fields=((), ()), history=history)
        if name in BOUNDS and self.bound_a is None:
            return replace(self, bound_a=BOUNDS[name], history=history)
        if name in BOUNDS and self.bound_b is None:
            return replace(self, bound_b=BOUNDS[name], holes=(ValueType.REAL,), history=history)

        production = PRODUCTIONS[action]
        fields = list(self.fields)
        fields[self.field_index] = fields[self.field_index] + (action,)
        holes = production.children + self.holes[1:]
        field_index = self.field_index
        if not holes:
            field_index += 1
            if field_index < self.field_count:
                holes = (
                    ValueType.BOOL
                    if self.template == "enumerative" and field_index == 1
                    else ValueType.REAL,
                )
        return replace(self, fields=tuple(fields), holes=holes, field_index=field_index, history=history)

    def build(self) -> GapGenerator:
        if not self.terminal:
            raise ValueError("cannot build an incomplete program")
        if self.template == "recursive":
            return RecursiveGenerator(parse_prefix(self.fields[0]), parse_prefix(self.fields[1]))
        if self.template == "enumerative":
            assert self.bound_a is not None and self.bound_b is not None
            return EnumerativeGenerator(
                self.bound_a,
                self.bound_b,
                parse_prefix(self.fields[0]),
                parse_prefix(self.fields[1]),
            )
        raise AssertionError("unknown template")

    def token_ids(self) -> tuple[int, ...]:
        # 0 is padding, 1 is BOS, grammar actions start at 2. State metadata
        # follows the action vocabulary so identical prefixes under different
        # templates/budgets are distinguishable to the model.
        metadata_base = len(PRODUCTIONS) + 2
        template_index = {None: 0, "recursive": 1, "enumerative": 2}[self.template]
        context_index = {None: 0, "init": 1, "next": 2, "element": 3, "keep": 4}[self.context]
        remaining = max(0, min(64, self.max_nodes - self.node_count))
        template_token = metadata_base + template_index
        context_token = metadata_base + 3 + context_index
        budget_token = metadata_base + 3 + 5 + remaining
        return (
            1,
            template_token,
            context_token,
            budget_token,
        ) + tuple(action + 2 for action in self.history)


VOCAB_SIZE = len(PRODUCTIONS) + 2 + 3 + 5 + 65
