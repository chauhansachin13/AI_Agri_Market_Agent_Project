"""Small dense linear algebra, in pure Python.

The ridge forecaster solves a normal-equation system with at most a few dozen
features, so a compact Cholesky solve is both sufficient and exact enough.
Keeping it dependency-free is what lets the trained forecaster run in the
default install, rather than being gated behind NumPy and PyTorch.

`numpy` is used when it is present, because it is faster and better
conditioned; the pure-Python path is a drop-in equivalent.
"""

from __future__ import annotations

Matrix = list[list[float]]
Vector = list[float]


def transpose(matrix: Matrix) -> Matrix:
    return [list(row) for row in zip(*matrix)] if matrix else []


def matmul(a: Matrix, b: Matrix) -> Matrix:
    if not a or not b:
        return []
    b_t = transpose(b)
    return [[sum(x * y for x, y in zip(row, col)) for col in b_t] for row in a]


def matvec(a: Matrix, v: Vector) -> Vector:
    return [sum(x * y for x, y in zip(row, v)) for row in a]


def identity(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def cholesky(matrix: Matrix) -> Matrix:
    """Lower-triangular L with L @ L.T == matrix, for symmetric positive definite input.

    Raises ValueError if the matrix is not positive definite, which the caller
    handles by increasing the ridge penalty.
    """
    n = len(matrix)
    lower: Matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1):
            total = sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                diagonal = matrix[i][i] - total
                if diagonal <= 1e-12:
                    raise ValueError("matrix is not positive definite")
                lower[i][j] = diagonal**0.5
            else:
                lower[i][j] = (matrix[i][j] - total) / lower[j][j]

    return lower


def solve_cholesky(matrix: Matrix, rhs: Vector) -> Vector:
    """Solve `matrix @ x = rhs` for symmetric positive definite `matrix`."""
    lower = cholesky(matrix)
    n = len(rhs)

    # Forward substitution: L y = rhs
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - sum(lower[i][k] * y[k] for k in range(i))) / lower[i][i]

    # Back substitution: L.T x = y
    x = [0.0] * n
    for i in reversed(range(n)):
        total = sum(lower[k][i] * x[k] for k in range(i + 1, n))
        x[i] = (y[i] - total) / lower[i][i]

    return x


def ridge_solve(design: Matrix, target: Vector, penalty: float) -> Vector:
    """Ridge regression coefficients: (XᵀX + λI)⁻¹ Xᵀy.

    The penalty is raised progressively if the system is ill-conditioned, which
    happens when lag features are near-collinear — common in a flat price
    series, so it must be handled rather than allowed to raise.
    """
    try:  # pragma: no cover - exercised only when numpy is installed
        import numpy as np

        x = np.asarray(design, dtype="float64")
        y = np.asarray(target, dtype="float64")
        gram = x.T @ x + penalty * np.eye(x.shape[1])
        return [float(value) for value in np.linalg.solve(gram, x.T @ y)]
    except Exception:
        # No numpy, or a singular system — fall through to the exact solve
        # below, which raises the penalty until the system is conditioned.
        pass

    design_t = transpose(design)
    gram = matmul(design_t, design)
    rhs = matvec(design_t, target)

    n = len(gram)
    current = penalty
    for _ in range(8):
        regularised = [
            [gram[i][j] + (current if i == j else 0.0) for j in range(n)] for i in range(n)
        ]
        try:
            return solve_cholesky(regularised, rhs)
        except ValueError:
            current = max(current * 10.0, 1e-6)

    return [0.0] * n


def mean(values: Vector) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: Vector) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    return (sum((v - mu) ** 2 for v in values) / (len(values) - 1)) ** 0.5
