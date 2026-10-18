"""Valid-by-construction bounded imperative gap-generator programs."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, replace
from typing import Literal

from .dsl import Expr, evaluate
from .shellsort import validate_gaps

StatementKind = Literal["assign", "emit"]
VARIABLES = ("n", "t", "last", "k", "r0", "r1", "r2", "r3")
CONSTANTS = (0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0)
UNARY_OPS = ("sqrt", "log", "floor", "ceil", "abs")
BINARY_OPS = ("add", "sub", "mul", "div", "mod", "min", "max", "pow")
PREDICATE_OPS = ("lt", "le", "eq")


@dataclass(frozen=True)
class Statement:
    kind: StatementKind
    expression: Expr
    target: int = 0
    predicate: Expr | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "target": self.target,
            "expression": self.expression.to_dict(),
            "predicate": self.predicate.to_dict() if self.predicate else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Statement":
        return cls(
            str(payload["kind"]),  # type: ignore[arg-type]
            Expr.from_dict(payload["expression"]),  # type: ignore[arg-type]
            int(payload.get("target", 0)),
            Expr.from_dict(payload["predicate"]) if payload.get("predicate") else None,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class GeneratorProgram:
    """One general bounded program; no mutually exclusive generator template."""

    initializers: tuple[Expr, ...]
    body: tuple[Statement, ...]
    fuel_base: int = 2
    fuel_log: int = 2
    max_outputs: int = 256

    def __post_init__(self) -> None:
        if not 1 <= len(self.initializers) <= 4:
            raise ValueError("programs need one to four registers")
        if not self.body or len(self.body) > 32:
            raise ValueError("program body must contain 1..32 statements")
        if not any(statement.kind == "emit" for statement in self.body):
            raise ValueError("program must contain an emit statement")
        if not 0 <= self.fuel_base <= 64 or not 1 <= self.fuel_log <= 16:
            raise ValueError("program fuel exceeds execution budget")
        for statement in self.body:
            if statement.kind not in {"assign", "emit"}:
                raise ValueError("unknown program statement")
            if statement.kind == "assign" and not 0 <= statement.target < len(self.initializers):
                raise ValueError("assignment register outside program state")

    @property
    def program_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def complexity(self) -> tuple[int, int]:
        expressions = list(self.initializers)
        for statement in self.body:
            expressions.append(statement.expression)
            if statement.predicate:
                expressions.append(statement.predicate)
        return (
            len(self.body) + sum(expr.size for expr in expressions),
            max(expr.depth for expr in expressions),
        )

    def generate(self, n: int) -> tuple[int, ...]:
        if n <= 1:
            return ()
        env: dict[str, float] = {"n": float(n), "t": 0.0, "last": 1.0, "k": 1.0}
        for index, expression in enumerate(self.initializers):
            env[f"r{index}"] = evaluate(expression, env, bound=max(1e6, n * n))
        for index in range(len(self.initializers), 4):
            env[f"r{index}"] = 0.0
        values = {1}
        fuel = min(512, self.fuel_base + self.fuel_log * math.ceil(math.log2(n + 1)))
        for step in range(fuel):
            env["t"] = float(step)
            for statement in self.body:
                allowed = statement.predicate is None or bool(evaluate(statement.predicate, env))
                if not allowed:
                    continue
                value = evaluate(statement.expression, env, bound=max(1e6, n * n))
                if statement.kind == "assign":
                    env[f"r{statement.target}"] = value
                else:
                    gap = math.floor(value)
                    if 1 <= gap < n:
                        values.add(gap)
                        env["last"] = float(gap)
                        env["k"] = float(len(values))
                    if len(values) >= self.max_outputs:
                        break
            if len(values) >= self.max_outputs:
                break
        return validate_gaps(tuple(sorted(values, reverse=True)), n)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "type": "bounded_imperative",
            "initializers": [item.to_dict() for item in self.initializers],
            "body": [item.to_dict() for item in self.body],
            "fuel_base": self.fuel_base,
            "fuel_log": self.fuel_log,
            "max_outputs": self.max_outputs,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "GeneratorProgram":
        if payload.get("schema_version") not in {1, 3} or payload.get("type") != "bounded_imperative":
            raise ValueError("unsupported generator schema")
        return cls(
            tuple(Expr.from_dict(x) for x in payload["initializers"]),  # type: ignore[arg-type]
            tuple(Statement.from_dict(x) for x in payload["body"]),  # type: ignore[arg-type]
            int(payload["fuel_base"]),
            int(payload["fuel_log"]),
            int(payload.get("max_outputs", 256)),
        )


def random_expr(rng: random.Random, register_count: int, depth: int = 3) -> Expr:
    variables = VARIABLES[:4] + VARIABLES[4 : 4 + register_count]
    if depth <= 1 or rng.random() < 0.38:
        if rng.random() < 0.65:
            return Expr.variable(rng.choice(variables))
        return Expr.constant(rng.choice(CONSTANTS) * math.exp(rng.gauss(0, 0.12)))
    if rng.random() < 0.25:
        return Expr(rng.choice(UNARY_OPS), (random_expr(rng, register_count, depth - 1),))
    return Expr(
        rng.choice(BINARY_OPS),
        (random_expr(rng, register_count, depth - 1), random_expr(rng, register_count, depth - 1)),
    )


def random_predicate(rng: random.Random, register_count: int, depth: int = 2) -> Expr:
    return Expr(
        rng.choice(PREDICATE_OPS),
        (random_expr(rng, register_count, depth), random_expr(rng, register_count, depth)),
    )


def random_program(rng: random.Random) -> GeneratorProgram:
    registers = rng.randint(1, 3)
    if rng.random() < 0.65:
        # A generic productive bootstrap, not a named sequence: initialize a
        # state from n, emit it, then update it with a random typed expression.
        divisor = Expr.constant(rng.uniform(1.5, 6.0))
        initializers = [Expr("div", (Expr.variable("n"), divisor))]
        initializers.extend(random_expr(rng, 0, 3) for _ in range(registers - 1))
        update = random_expr(rng, registers, 3)
        if rng.random() < 0.7:
            update = Expr("div", (Expr.variable("r0"), Expr.constant(rng.uniform(1.2, 4.0))))
        body = [Statement("emit", Expr.variable("r0")), Statement("assign", update, 0)]
        if rng.random() < 0.5:
            body.insert(1, Statement("emit", random_expr(rng, registers, 3)))
        return GeneratorProgram(tuple(initializers), tuple(body), rng.randint(0, 3), rng.randint(1, 4))
    initializers = tuple(random_expr(rng, 0, 3) for _ in range(registers))
    body: list[Statement] = []
    for _ in range(rng.randint(2, 6)):
        kind: StatementKind = "emit" if rng.random() < 0.55 else "assign"
        body.append(
            Statement(
                kind,
                random_expr(rng, registers, rng.randint(2, 4)),
                rng.randrange(registers),
                random_predicate(rng, registers) if rng.random() < 0.25 else None,
            )
        )
    if not any(item.kind == "emit" for item in body):
        body.append(Statement("emit", Expr.variable("r0")))
    return GeneratorProgram(initializers, tuple(body), rng.randint(0, 4), rng.randint(1, 4))


MUTATION_KINDS = (
    "replace_expression",
    "insert_emit",
    "insert_assign",
    "delete_statement",
    "toggle_predicate",
    "mutate_constant",
    "change_fuel",
    "duplicate_statement",
)


def _mutate_constants(expr: Expr, rng: random.Random) -> Expr:
    if expr.op == "const":
        return Expr.constant(float(expr.value) * math.exp(rng.gauss(0, 0.2)) + rng.gauss(0, 0.1))
    if not expr.args:
        return expr
    index = rng.randrange(len(expr.args))
    args = list(expr.args)
    args[index] = _mutate_constants(args[index], rng)
    return Expr(expr.op, tuple(args), expr.value)


def mutate_program(
    program: GeneratorProgram, kind: str, rng: random.Random
) -> GeneratorProgram:
    if kind not in MUTATION_KINDS:
        raise ValueError(f"unknown mutation: {kind}")
    initializers = list(program.initializers)
    body = list(program.body)
    registers = len(initializers)
    if kind == "replace_expression":
        if rng.random() < 0.3:
            index = rng.randrange(registers)
            initializers[index] = random_expr(rng, 0, rng.randint(2, 5))
        else:
            index = rng.randrange(len(body))
            body[index] = replace(body[index], expression=random_expr(rng, registers, rng.randint(2, 5)))
    elif kind == "insert_emit" and len(body) < 32:
        body.insert(rng.randrange(len(body) + 1), Statement(
            "emit", random_expr(rng, registers, rng.randint(2, 5)), 0,
            random_predicate(rng, registers) if rng.random() < 0.35 else None,
        ))
    elif kind == "insert_assign" and len(body) < 32:
        body.insert(rng.randrange(len(body) + 1), Statement(
            "assign", random_expr(rng, registers, rng.randint(2, 5)), rng.randrange(registers),
            random_predicate(rng, registers) if rng.random() < 0.25 else None,
        ))
    elif kind == "delete_statement" and len(body) > 1:
        removable = [i for i in range(len(body)) if body[i].kind != "emit" or sum(x.kind == "emit" for x in body) > 1]
        if removable:
            del body[rng.choice(removable)]
    elif kind == "toggle_predicate":
        index = rng.randrange(len(body))
        predicate = None if body[index].predicate else random_predicate(rng, registers, 3)
        body[index] = replace(body[index], predicate=predicate)
    elif kind == "mutate_constant":
        index = rng.randrange(len(body))
        body[index] = replace(body[index], expression=_mutate_constants(body[index].expression, rng))
    elif kind == "change_fuel":
        return replace(
            program,
            fuel_base=max(0, min(64, program.fuel_base + rng.choice((-1, 1)))),
            fuel_log=max(1, min(16, program.fuel_log + rng.choice((-1, 1)))),
        )
    elif kind == "duplicate_statement" and len(body) < 32:
        index = rng.randrange(len(body))
        body.insert(index, body[index])
    candidate = GeneratorProgram(tuple(initializers), tuple(body), program.fuel_base, program.fuel_log)
    return candidate
