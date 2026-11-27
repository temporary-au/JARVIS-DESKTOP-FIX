"""Offline mathematics engine for JARVIS.

Uses a deliberately small AST allow-list (never eval) to turn user expressions
into SymPy objects. SymPy handles exact/symbolic work; NumPy/SciPy are available
for future numerical extensions and are reported in diagnostics.
"""
from __future__ import annotations

import ast
import re
from typing import Any

try:
    import sympy as sp
except Exception:  # Keep ordinary JARVIS startup usable if optional math deps fail.
    sp = None


class UnsafeMathExpression(ValueError):
    pass


class MathEngine:
    FUNCTIONS = {
        "sqrt": lambda x: sp.sqrt(x), "sin": lambda x: sp.sin(x),
        "cos": lambda x: sp.cos(x), "tan": lambda x: sp.tan(x),
        "asin": lambda x: sp.asin(x), "acos": lambda x: sp.acos(x),
        "atan": lambda x: sp.atan(x), "log": lambda x: sp.log(x),
        "ln": lambda x: sp.log(x), "exp": lambda x: sp.exp(x),
        "abs": lambda x: sp.Abs(x), "factorial": lambda x: sp.factorial(x),
    }
    CONSTANTS = {"pi": sp.pi, "e": sp.E, "oo": sp.oo} if sp else {}

    def __init__(self):
        if sp is None:
            raise RuntimeError("SymPy is not installed. Rebuild JARVIS with the mathematics requirements.")

    def expression(self, source: str):
        source = source.strip().replace("^", "**").replace("π", "pi")
        if not source or len(source) > 500:
            raise ValueError("The mathematical expression is empty or too long.")
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as exc:
            raise ValueError("I couldn't parse that expression. Use standard notation, for example (x^2 + 1)/(x - 1).") from exc
        return self._node(tree.body)

    def _node(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)
        if isinstance(node, ast.Name):
            if node.id in self.CONSTANTS:
                return self.CONSTANTS[node.id]
            if len(node.id) > 24 or not node.id.isidentifier():
                raise UnsafeMathExpression("Invalid symbol name.")
            return sp.Symbol(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._node(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left), self._node(node.right)
            ops = {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                   ast.Mult: lambda: left * right, ast.Div: lambda: left / right,
                   ast.Pow: lambda: left ** right, ast.Mod: lambda: sp.Mod(left, right)}
            for kind, operation in ops.items():
                if isinstance(node.op, kind):
                    if isinstance(node.op, ast.Pow) and right.is_number and abs(float(right)) > 1000:
                        raise ValueError("Exponent is too large for the offline maths engine.")
                    return operation()
            raise UnsafeMathExpression("That operator is not supported.")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.FUNCTIONS and len(node.args) == 1 and not node.keywords:
            return self.FUNCTIONS[node.func.id](self._node(node.args[0]))
        raise UnsafeMathExpression("Only arithmetic, symbols and approved maths functions are allowed.")

    @staticmethod
    def _fmt(value) -> str:
        return str(value)

    def solve(self, prompt: str) -> str | None:
        q = prompt.strip()
        low = q.lower()
        try:
            # Derivatives
            m = re.search(r"(?:differentiat(?:e|ion)\s+(?:of\s+)?|derivative\s+of\s+|d/d([a-z])\s*)(.+?)(?:\s+with\s+respect\s+to\s+([a-z]))?$", q, re.I)
            if m and any(w in low for w in ("differentiat", "derivative", "d/d")):
                if low.startswith("d/d"):
                    var, expr_text = m.group(1), m.group(2)
                else:
                    expr_text, var = m.group(2), (m.group(3) or "x")
                expr = self.expression(expr_text.strip(" :?"))
                symbol = sp.Symbol(var)
                result = sp.diff(expr, symbol)
                return f"**Symbolic differentiation**\n\nExpression: `{sp.latex(expr)}`\n\nWith respect to: `{var}`\n\nDerivative: `{sp.latex(result)}`\n\nResult: `{result}`"

            # Integrals
            m = re.search(r"(?:integrat(?:e|ion)\s+(?:of\s+)?|integral\s+of\s+)(.+?)(?:\s+with\s+respect\s+to\s+([a-z]))?$", q, re.I)
            if m and any(w in low for w in ("integrat", "integral")):
                expr = self.expression(m.group(1).strip(" :?")); var = m.group(2) or "x"
                result = sp.integrate(expr, sp.Symbol(var))
                return f"**Symbolic integration**\n\nIntegrand: `{expr}`\n\nVariable: `{var}`\n\nAntiderivative: `{result} + C`"

            # Limits: limit of expression as x approaches value
            m = re.search(r"limit\s+of\s+(.+?)\s+as\s+([a-z])\s*(?:->|approaches?)\s*([^\s?]+)", q, re.I)
            if m:
                expr = self.expression(m.group(1).strip(" :?")); var = sp.Symbol(m.group(2)); point = self.expression(m.group(3))
                result = sp.limit(expr, var, point)
                return f"**Limit**\n\nExpression: `{expr}`\n\nAs `{var} → {point}`\n\nResult: `{result}`"

            # Solve equation for variable
            m = re.search(r"solve\s+(.+?)\s+for\s+([a-z])\s*\??$", q, re.I)
            if m:
                equation_text, var = m.group(1), m.group(2)
                if "=" not in equation_text:
                    raise ValueError("For solving, include an equation such as 2*x + 3 = 7.")
                left, right = equation_text.split("=", 1)
                equation = sp.Eq(self.expression(left), self.expression(right))
                result = sp.solve(equation, sp.Symbol(var))
                return f"**Equation solving**\n\nEquation: `{sp.sstr(equation)}`\n\nSolve for: `{var}`\n\nSolution: `{result}`"

            # Factor / expand / simplify
            for verb, fn, heading in (("factor", sp.factor, "Factorisation"), ("expand", sp.expand, "Expansion"), ("simplify", sp.simplify, "Simplification")):
                m = re.search(rf"{verb}\s+(.+?)[?]?$", q, re.I)
                if m:
                    expr = self.expression(m.group(1).strip(" :?")); result = fn(expr)
                    return f"**{heading}**\n\nInput: `{expr}`\n\nResult: `{result}`"

            # Explicit arithmetic/calculation prompts.
            m = re.search(r"(?:calculate|compute|evaluate|what\s+is)\s+(.+?)[?]?$", q, re.I)
            if m:
                expr = self.expression(m.group(1).strip(" :?"))
                result = sp.simplify(expr)
                if not result.free_symbols:
                    result = sp.N(result, 15) if result.is_Float else result
                return f"**Calculation**\n\nExpression: `{expr}`\n\nResult: `{result}`"
        except Exception as exc:
            return f"I recognised this as a maths request, but couldn't safely complete it: {exc}"
        return None
