"""Safe offline symbolic/numeric mathematics for JARVIS.

The parser accepts a deliberately limited mathematical grammar and never calls
Python eval/exec. SymPy performs the actual symbolic calculations.
"""
from __future__ import annotations
import ast
import re

try:
    import sympy as sp
except Exception:
    sp = None


class UnsafeMathExpression(ValueError):
    pass


class MathEngine:
    MAX_SOURCE = 1000
    FUNCTIONS = {
        "sqrt": sp.sqrt if sp else None, "sin": sp.sin if sp else None,
        "cos": sp.cos if sp else None, "tan": sp.tan if sp else None,
        "asin": sp.asin if sp else None, "acos": sp.acos if sp else None,
        "atan": sp.atan if sp else None, "sinh": sp.sinh if sp else None,
        "cosh": sp.cosh if sp else None, "tanh": sp.tanh if sp else None,
        "log": sp.log if sp else None, "ln": sp.log if sp else None,
        "exp": sp.exp if sp else None, "abs": sp.Abs if sp else None,
        "factorial": sp.factorial if sp else None,
        "floor": sp.floor if sp else None, "ceil": sp.ceiling if sp else None,
        "Matrix": sp.Matrix if sp else None,
        "det": (lambda value: sp.Matrix(value).det()) if sp else None,
        "determinant": (lambda value: sp.Matrix(value).det()) if sp else None,
        "inverse": (lambda value: sp.Matrix(value).inv()) if sp else None,
        "rank": (lambda value: sp.Matrix(value).rank()) if sp else None,
        "trace": (lambda value: sp.Matrix(value).trace()) if sp else None,
        "eigenvalues": (lambda value: sp.Matrix(value).eigenvals()) if sp else None,
        "transpose": (lambda value: sp.Matrix(value).T) if sp else None,
        "summation": (lambda expr, var, start, end: sp.summation(expr, (var, start, end))) if sp else None,
        "product": (lambda expr, var, start, end: sp.product(expr, (var, start, end))) if sp else None,
        "binomial": sp.binomial if sp else None,
    }
    CONSTANTS = {"pi": sp.pi, "e": sp.E, "I": sp.I, "oo": sp.oo, "zoo": sp.zoo} if sp else {}

    def __init__(self):
        # Keep the desktop app usable if a maths dependency is missing. The
        # build workflow separately verifies SymPy is packaged correctly.
        self.available = sp is not None

    @staticmethod
    def _insert_implicit_multiplication(source: str) -> str:
        # Tokenise only mathematical names, numbers and operators. This is not
        # Python tokenisation and does not permit attribute access or strings.
        pattern = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|\*\*|<=|>=|==|!=|[()[\]+\-*/%^!,=,]")
        tokens = pattern.findall(source)
        if "".join(tokens).replace(" ", "") != re.sub(r"\s+", "", source):
            raise UnsafeMathExpression("Use mathematical symbols and standard operators only.")
        out = []
        for i, token in enumerate(tokens):
            if i:
                prev = tokens[i - 1]
                prev_ends_value = bool(re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[)]", prev))
                next_starts_value = bool(re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[(]", token))
                is_function_call = prev in MathEngine.FUNCTIONS and token == "("
                is_constant_call = prev in MathEngine.CONSTANTS and token == "("
                if prev_ends_value and next_starts_value and not is_function_call and not is_constant_call:
                    out.append("*")
            out.append(token)
        return "".join(out)

    def expression(self, source: str):
        source = str(source).strip()
        source = (source.replace("^", "**").replace("×", "*").replace("÷", "/")
                  .replace("−", "-").replace("π", "pi").replace("∞", "oo")
                  .replace("²", "**2").replace("³", "**3").replace("⁴", "**4"))
        if not source or len(source) > self.MAX_SOURCE:
            raise ValueError("The mathematical expression is empty or too long.")
        source = self._insert_implicit_multiplication(source)
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as exc:
            raise ValueError("I couldn't understand the mathematical notation. Try an expression such as 2*x, (x^2+1)/(x-1), or sin(pi/2).") from exc
        return self._node(tree.body)

    def _node(self, node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)
        if isinstance(node, ast.Name):
            if node.id in self.CONSTANTS:
                return self.CONSTANTS[node.id]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,23}", node.id):
                raise UnsafeMathExpression("Invalid mathematical symbol.")
            return sp.Symbol(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._node(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left), self._node(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
            if isinstance(node.op, ast.Mod): return sp.Mod(left, right)
            if isinstance(node.op, ast.Pow):
                if right.is_number and abs(float(right)) > 1000:
                    raise ValueError("Exponent is too large for the offline maths engine.")
                return left ** right
            raise UnsafeMathExpression("That mathematical operator is not supported.")
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._node(item) for item in node.elts]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = self.FUNCTIONS.get(node.func.id)
            if fn is None or not 1 <= len(node.args) <= 4 or node.keywords:
                raise UnsafeMathExpression("That function is not supported.")
            return fn(*(self._node(arg) for arg in node.args))
        raise UnsafeMathExpression("Only mathematical expressions and approved functions are allowed.")

    @staticmethod
    def _clean_expr(text: str) -> str:
        return text.strip().strip(" :?=;")

    def solve(self, prompt: str) -> str | None:
        if sp is None:
            return None
        q = str(prompt).strip()
        low = q.lower()
        try:
            # Normalise common natural-language wrappers before parsing.
            definite = re.match(r"^(?:evaluate\s+)?integrate\s+(.+?)\s+from\s+([^\s]+)\s+to\s+([^\s]+)\??$", q, re.I)
            if definite:
                expr = self.expression(definite.group(1))
                lower = self.expression(definite.group(2))
                upper = self.expression(definite.group(3))
                result = sp.integrate(expr, (sp.Symbol("x"), lower, upper))
                return f"**Definite integral**\n\nResult: `{sp.sstr(result)}`"

            patterns = [
                (r"^(?:please\s+)?(?:differentiate|find the derivative of|derivative of|what is the derivative of)(?:\s+the)?(?:\s+(?:function|expression))?\s+(.+?)(?:\s+with respect to\s+([a-z]))?\??$", "diff"),
                (r"^(?:please\s+)?(?:integrate|find the integral of|integral of|what is the integral of)(?:\s+the)?(?:\s+(?:function|expression))?\s+(.+?)(?:\s+with respect to\s+([a-z]))?\??$", "integrate"),
            ]
            for pattern, kind in patterns:
                m = re.match(pattern, q, re.I)
                if m:
                    expr = self.expression(self._clean_expr(m.group(1)))
                    var = sp.Symbol(m.group(2) or "x")
                    result = sp.diff(expr, var) if kind == "diff" else sp.integrate(expr, var)
                    label = "Derivative" if kind == "diff" else "Antiderivative"
                    suffix = "" if kind == "diff" else " + C"
                    return f"**{label}**\n\nExpression: `{sp.sstr(expr)}`\n\nWith respect to: `{var}`\n\nResult: `{sp.sstr(result)}{suffix}`"

            m = re.match(r"^d/d([a-z])\s*(.+)$", q, re.I)
            if m:
                var, expr_text = m.group(1), m.group(2)
                expr = self.expression(self._clean_expr(expr_text))
                result = sp.diff(expr, sp.Symbol(var))
                return f"**Derivative**\n\nResult: `{sp.sstr(result)}`"

            m = re.match(r"^(?:limit of\s+)(.+?)\s+as\s+([a-z])\s*(?:->|→|approaches?)\s*([^\s?]+)\??$", q, re.I)
            if m:
                expr = self.expression(m.group(1)); var = sp.Symbol(m.group(2)); point = self.expression(m.group(3))
                return f"**Limit**\n\n\\lim_{{{var}\\to {sp.latex(point)}}} {sp.latex(expr)} = `{sp.sstr(sp.limit(expr, var, point))}`"

            # Linear/nonlinear systems: separate equations with semicolons.
            system_match = re.match(r"^solve\s+(?:system:?\s*)?(.+?)\s+for\s+([a-z,\s]+)\??$", q, re.I)
            if system_match and ";" in system_match.group(1):
                equations_text = [part.strip() for part in system_match.group(1).split(";") if part.strip()]
                variables = [sp.Symbol(name.strip()) for name in system_match.group(2).split(",") if name.strip()]
                equations = []
                for equation_text in equations_text:
                    if "=" not in equation_text:
                        raise ValueError("Each equation in a system must contain =.")
                    left_text, right_text = equation_text.split("=", 1)
                    equations.append(sp.Eq(self.expression(left_text), self.expression(right_text)))
                result = sp.solve(equations, variables, dict=True)
                return f"**System of equations**\n\nSolutions: `{sp.sstr(result)}`"

            m = re.match(r"^(?:solve\s+)?(.+?)\s*=\s*(.+?)\s+(?:for\s+([a-z]))\??$", q, re.I)
            if not m:
                m = re.match(r"^solve\s+(.+?)\s*=\s*(.+?)\??$", q, re.I)
            if m:
                left = self.expression(m.group(1)); right = self.expression(m.group(2))
                var = sp.Symbol(m.group(3) or "x")
                solutions = sp.solve(sp.Eq(left, right), var)
                return f"**Equation solving**\n\nEquation: `{sp.sstr(left)} = {sp.sstr(right)}`\n\nVariable: `{var}`\n\nSolutions: `{sp.sstr(solutions)}`"

            for verb, fn, heading in (("factor", sp.factor, "Factorisation"), ("expand", sp.expand, "Expansion"), ("simplify", sp.simplify, "Simplification")):
                m = re.match(rf"^(?:please\s+)?{verb}\s+(.+?)\??$", q, re.I)
                if m:
                    expr = self.expression(self._clean_expr(m.group(1)))
                    return f"**{heading}**\n\nInput: `{sp.sstr(expr)}`\n\nResult: `{sp.sstr(fn(expr))}`"

            m = re.match(r"^(?:determinant|det|inverse|rank|trace|eigenvalues)\s+of\s+(.+?)\??$", q, re.I)
            if m:
                verb = low.split()[0]
                matrix = self.expression(m.group(1))
                operation = {"determinant": sp.Matrix(matrix).det, "det": sp.Matrix(matrix).det,
                             "inverse": sp.Matrix(matrix).inv, "rank": sp.Matrix(matrix).rank,
                             "trace": sp.Matrix(matrix).trace, "eigenvalues": sp.Matrix(matrix).eigenvals}[verb]
                return f"**Matrix {verb}**\n\nResult: `{sp.sstr(operation())}`"

            m = re.match(r"^(?:calculate|compute|evaluate|what is|work out)\s+(.+?)\??$", q, re.I)
            if m:
                expr = self.expression(self._clean_expr(m.group(1)))
                result = sp.simplify(expr)
                if not result.free_symbols:
                    result = sp.N(result, 15) if result.is_Float else result
                return f"**Calculation**\n\nExpression: `{sp.sstr(expr)}`\n\nResult: `{sp.sstr(result)}`"

            # A bare expression is treated as maths only when it contains an
            # operator/digit and no prose. This avoids hijacking ordinary chat.
            if re.fullmatch(r"[\w\sπ∞.+\-*/^%(),\[\]×÷−]+", q) and re.search(r"\d|[+*/^%()]", q):
                expr = self.expression(q)
                result = sp.simplify(expr)
                if not result.free_symbols: result = sp.N(result, 15) if result.is_Float else result
                return f"**Calculation**\n\nExpression: `{sp.sstr(expr)}`\n\nResult: `{sp.sstr(result)}`"
        except Exception:
            # Let the language model attempt a safe explanation when a valid
            # problem falls outside this deterministic parser's grammar.
            # It is instructed not to invent a result when it cannot verify it.
            return None
        return None
