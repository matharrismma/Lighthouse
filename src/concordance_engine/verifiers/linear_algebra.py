"""Linear algebra verifier.

Vector and matrix operations. All math is computed deterministically
via NumPy; no values are taken on authority. Claims that close from
the matrix algebra come back CONFIRMED with the actual computed
result displayed; claims that don't come back MISMATCH with the
correct value.

Checks:
  * vector.dot_product        — a · b
  * vector.cross_product      — a × b (R³ only)
  * vector.magnitude          — |v|
  * vector.angle              — θ between two vectors
  * matrix.addition           — A + B
  * matrix.multiplication     — A B  (and matrix-vector A v)
  * matrix.determinant        — det A
  * matrix.trace              — tr A
  * matrix.inverse_check      — verify A · A_claimed_inverse = I
  * matrix.eigenvalues        — characteristic polynomial roots
  * system.solve_check        — verify A x_claimed = b

LIN_VERIFY shape (any subset; each check fires when its keys are present):

    # vector ops
    {"vec_a": [1,2,3], "vec_b": [4,5,6], "claimed_dot_product": 32}
    {"vec_a": [1,0,0], "vec_b": [0,1,0], "claimed_cross_product": [0,0,1]}
    {"vec": [3,4], "claimed_magnitude": 5}
    {"vec_a": [1,0], "vec_b": [0,1], "claimed_angle_deg": 90}

    # matrix ops
    {"mat_a": [[1,2],[3,4]], "mat_b": [[5,6],[7,8]],
     "claimed_matrix_sum": [[6,8],[10,12]]}
    {"mat_a": [[1,2],[3,4]], "mat_b": [[5,6],[7,8]],
     "claimed_matrix_product": [[19,22],[43,50]]}
    {"matrix": [[1,2],[3,4]], "claimed_determinant": -2}
    {"matrix": [[1,2],[3,4]], "claimed_trace": 5}
    {"matrix": [[2,0],[0,3]], "claimed_eigenvalues": [2,3]}
    {"matrix": [[1,2],[3,4]], "claimed_inverse": [[-2,1],[1.5,-0.5]]}
    {"matrix": [[1,2],[3,4]], "vec_b": [5,11], "claimed_solution": [1,2]}
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base import VerifierResult, na, confirm, mismatch, error


# ── helpers ─────────────────────────────────────────────────────────────

def _as_vec(v: Any) -> Optional[np.ndarray]:
    """Coerce input to a 1-D numpy array, or None on failure."""
    if v is None:
        return None
    try:
        arr = np.asarray(v, dtype=float)
        if arr.ndim != 1:
            return None
        return arr
    except Exception:
        return None


def _as_mat(m: Any) -> Optional[np.ndarray]:
    """Coerce input to a 2-D numpy array, or None on failure."""
    if m is None:
        return None
    try:
        arr = np.asarray(m, dtype=float)
        if arr.ndim != 2:
            return None
        return arr
    except Exception:
        return None


def _close(a: float, b: float, rel: float = 1e-6, abs_: float = 1e-9) -> bool:
    """Element-wise float comparison with relative + absolute tolerance."""
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def _arrays_close(a: np.ndarray, b: np.ndarray,
                  rel: float = 1e-6, abs_: float = 1e-9) -> bool:
    """np.allclose with sensible defaults."""
    return bool(np.allclose(a, b, rtol=rel, atol=abs_))


# ── Vector checks ──────────────────────────────────────────────────────

def verify_vector_dot(spec: Dict[str, Any]) -> VerifierResult:
    name = "vector.dot_product"
    a = _as_vec(spec.get("vec_a"))
    b = _as_vec(spec.get("vec_b"))
    claimed = spec.get("claimed_dot_product")
    if a is None or b is None or claimed is None:
        return na(name)
    if a.shape != b.shape:
        return error(name, f"vec_a and vec_b must have same length, got {a.shape} and {b.shape}")
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_dot_product must be numeric")
    actual = float(np.dot(a, b))
    data = {"vec_a": a.tolist(), "vec_b": b.tolist(),
            "actual_dot": actual, "claimed_dot": cl,
            "formula": "a · b = Σ aᵢ bᵢ"}
    if _close(actual, cl):
        return confirm(name, f"{a.tolist()} · {b.tolist()} = {actual}", data)
    return mismatch(name, f"{a.tolist()} · {b.tolist()} = {actual}, claimed {cl}", data)


def verify_vector_cross(spec: Dict[str, Any]) -> VerifierResult:
    name = "vector.cross_product"
    a = _as_vec(spec.get("vec_a"))
    b = _as_vec(spec.get("vec_b"))
    claimed = spec.get("claimed_cross_product")
    if a is None or b is None or claimed is None:
        return na(name)
    if a.shape != (3,) or b.shape != (3,):
        return error(name, f"cross product requires 3-element vectors; got {a.shape}, {b.shape}")
    cl = _as_vec(claimed)
    if cl is None or cl.shape != (3,):
        return error(name, "claimed_cross_product must be a 3-element vector")
    actual = np.cross(a, b)
    data = {"vec_a": a.tolist(), "vec_b": b.tolist(),
            "actual_cross": actual.tolist(), "claimed_cross": cl.tolist(),
            "formula": "a × b (right-hand rule)"}
    if _arrays_close(actual, cl):
        return confirm(name, f"{a.tolist()} × {b.tolist()} = {actual.tolist()}", data)
    return mismatch(name, f"{a.tolist()} × {b.tolist()} = {actual.tolist()}, claimed {cl.tolist()}", data)


def verify_vector_magnitude(spec: Dict[str, Any]) -> VerifierResult:
    name = "vector.magnitude"
    v = _as_vec(spec.get("vec"))
    claimed = spec.get("claimed_magnitude")
    if v is None or claimed is None:
        return na(name)
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_magnitude must be numeric")
    actual = float(np.linalg.norm(v))
    data = {"vec": v.tolist(),
            "actual_magnitude": actual, "claimed_magnitude": cl,
            "formula": "|v| = √(Σ vᵢ²)"}
    if _close(actual, cl):
        return confirm(name, f"|{v.tolist()}| = {actual}", data)
    return mismatch(name, f"|{v.tolist()}| = {actual}, claimed {cl}", data)


def verify_vector_angle(spec: Dict[str, Any]) -> VerifierResult:
    name = "vector.angle"
    a = _as_vec(spec.get("vec_a"))
    b = _as_vec(spec.get("vec_b"))
    claimed = spec.get("claimed_angle_deg")
    if a is None or b is None or claimed is None:
        return na(name)
    if a.shape != b.shape:
        return error(name, f"vectors must have same length, got {a.shape}, {b.shape}")
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return error(name, "cannot compute angle with zero vector")
    cos_theta = float(np.dot(a, b) / (norm_a * norm_b))
    cos_theta = max(-1.0, min(1.0, cos_theta))  # numerical safety
    actual_deg = float(np.degrees(np.arccos(cos_theta)))
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_angle_deg must be numeric")
    data = {"vec_a": a.tolist(), "vec_b": b.tolist(),
            "actual_angle_deg": actual_deg, "claimed_angle_deg": cl,
            "formula": "θ = arccos((a·b) / (|a| |b|))"}
    if abs(actual_deg - cl) <= 0.5:  # half-degree tolerance
        return confirm(name, f"angle = {actual_deg:.3f}° between vectors", data)
    return mismatch(name, f"actual angle {actual_deg:.3f}°, claimed {cl}°", data)


# ── Matrix checks ──────────────────────────────────────────────────────

def verify_matrix_addition(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.addition"
    A = _as_mat(spec.get("mat_a"))
    B = _as_mat(spec.get("mat_b"))
    claimed = spec.get("claimed_matrix_sum")
    if A is None or B is None or claimed is None:
        return na(name)
    if A.shape != B.shape:
        return error(name, f"matrix shapes must match, got {A.shape}, {B.shape}")
    cl = _as_mat(claimed)
    if cl is None or cl.shape != A.shape:
        return error(name, "claimed_matrix_sum shape must match")
    actual = A + B
    data = {"A": A.tolist(), "B": B.tolist(),
            "actual_sum": actual.tolist(), "claimed_sum": cl.tolist(),
            "formula": "(A+B)ᵢⱼ = Aᵢⱼ + Bᵢⱼ"}
    if _arrays_close(actual, cl):
        return confirm(name, f"A + B computed; matches claimed {A.shape}", data)
    return mismatch(name, f"actual A+B = {actual.tolist()}, claimed {cl.tolist()}", data)


def verify_matrix_multiplication(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.multiplication"
    A = _as_mat(spec.get("mat_a"))
    B = _as_mat(spec.get("mat_b"))
    claimed = spec.get("claimed_matrix_product")
    if A is None or B is None or claimed is None:
        return na(name)
    if A.shape[1] != B.shape[0]:
        return error(name, f"A is {A.shape}, B is {B.shape}; inner dimensions don't match")
    cl = _as_mat(claimed)
    if cl is None or cl.shape != (A.shape[0], B.shape[1]):
        return error(name, f"claimed_matrix_product shape must be {(A.shape[0], B.shape[1])}")
    actual = A @ B
    data = {"A": A.tolist(), "B": B.tolist(),
            "actual_product": actual.tolist(), "claimed_product": cl.tolist(),
            "formula": "(AB)ᵢⱼ = Σₖ Aᵢₖ Bₖⱼ"}
    if _arrays_close(actual, cl):
        return confirm(name, f"A·B = {actual.tolist()}", data)
    return mismatch(name, f"actual A·B = {actual.tolist()}, claimed {cl.tolist()}", data)


def verify_matrix_determinant(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.determinant"
    A = _as_mat(spec.get("matrix"))
    claimed = spec.get("claimed_determinant")
    if A is None or claimed is None:
        return na(name)
    if A.shape[0] != A.shape[1]:
        return error(name, f"determinant requires square matrix, got {A.shape}")
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_determinant must be numeric")
    actual = float(np.linalg.det(A))
    data = {"matrix": A.tolist(),
            "actual_determinant": actual, "claimed_determinant": cl,
            "formula": "det A (Laplace expansion or LU)"}
    if _close(actual, cl, rel=1e-5, abs_=1e-9):
        return confirm(name, f"det = {actual:.6g}", data)
    return mismatch(name, f"actual det = {actual:.6g}, claimed {cl}", data)


def verify_matrix_trace(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.trace"
    A = _as_mat(spec.get("matrix"))
    claimed = spec.get("claimed_trace")
    if A is None or claimed is None:
        return na(name)
    if A.shape[0] != A.shape[1]:
        return error(name, f"trace requires square matrix, got {A.shape}")
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_trace must be numeric")
    actual = float(np.trace(A))
    data = {"matrix": A.tolist(),
            "actual_trace": actual, "claimed_trace": cl,
            "formula": "tr(A) = Σᵢ Aᵢᵢ"}
    if _close(actual, cl):
        return confirm(name, f"tr = {actual}", data)
    return mismatch(name, f"actual tr = {actual}, claimed {cl}", data)


def verify_matrix_eigenvalues(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.eigenvalues"
    A = _as_mat(spec.get("matrix"))
    claimed = spec.get("claimed_eigenvalues")
    if A is None or claimed is None:
        return na(name)
    if A.shape[0] != A.shape[1]:
        return error(name, f"eigenvalues require square matrix, got {A.shape}")
    cl_arr = np.asarray(claimed, dtype=complex)
    if cl_arr.ndim != 1 or cl_arr.shape[0] != A.shape[0]:
        return error(name, f"claimed_eigenvalues must be a list of length {A.shape[0]}")
    actual = np.linalg.eigvals(A)
    # Match each claimed eigenvalue to a unique actual one. Sort by real part
    # then imaginary part to canonicalize.
    actual_sorted = sorted(actual, key=lambda x: (x.real, x.imag))
    claimed_sorted = sorted(cl_arr, key=lambda x: (x.real, x.imag))
    ok = all(abs(a - b) <= 1e-5 for a, b in zip(actual_sorted, claimed_sorted))
    # Represent results without complex-only outputs when imaginary parts are zero
    def _disp(z):
        return float(z.real) if abs(z.imag) < 1e-9 else (float(z.real), float(z.imag))
    data = {"matrix": A.tolist(),
            "actual_eigenvalues": [_disp(z) for z in actual_sorted],
            "claimed_eigenvalues": [_disp(z) for z in claimed_sorted],
            "formula": "det(A - λI) = 0"}
    if ok:
        return confirm(name, f"eigenvalues match (sorted): {data['actual_eigenvalues']}", data)
    return mismatch(name, f"actual eigenvalues {data['actual_eigenvalues']}, claimed {data['claimed_eigenvalues']}", data)


def verify_matrix_inverse(spec: Dict[str, Any]) -> VerifierResult:
    name = "matrix.inverse_check"
    A = _as_mat(spec.get("matrix"))
    cl = _as_mat(spec.get("claimed_inverse"))
    if A is None or cl is None:
        return na(name)
    if A.shape[0] != A.shape[1] or A.shape != cl.shape:
        return error(name, "matrix and claimed_inverse must both be square and same shape")
    product = A @ cl
    identity = np.eye(A.shape[0])
    data = {"matrix": A.tolist(), "claimed_inverse": cl.tolist(),
            "A_times_claimed": product.tolist(),
            "formula": "A · A⁻¹ = I"}
    if _arrays_close(product, identity, rel=1e-5, abs_=1e-7):
        return confirm(name, f"A · claimed_inverse = I (within tolerance)", data)
    return mismatch(name, f"A · claimed_inverse ≠ I; got {product.tolist()}", data)


def verify_linear_system(spec: Dict[str, Any]) -> VerifierResult:
    name = "system.solve_check"
    A = _as_mat(spec.get("matrix"))
    b = _as_vec(spec.get("vec_b"))
    x = _as_vec(spec.get("claimed_solution"))
    if A is None or b is None or x is None:
        return na(name)
    if A.shape[0] != b.shape[0] or A.shape[1] != x.shape[0]:
        return error(name, f"shapes incompatible: A={A.shape} b={b.shape} x={x.shape}")
    actual_b = A @ x
    data = {"matrix": A.tolist(), "claimed_solution": x.tolist(),
            "b_target": b.tolist(), "A_times_x": actual_b.tolist(),
            "formula": "A x = b"}
    if _arrays_close(actual_b, b, rel=1e-5, abs_=1e-7):
        return confirm(name, f"A x = b verified ({b.tolist()})", data)
    return mismatch(name, f"A·x = {actual_b.tolist()}, claimed solution gives wrong b (target {b.tolist()})", data)


# ── Dispatcher ─────────────────────────────────────────────────────────

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    lv = packet.get("LIN_VERIFY") or {}
    # Vectors
    if lv.get("vec_a") is not None and lv.get("vec_b") is not None:
        if lv.get("claimed_dot_product") is not None:
            results.append(verify_vector_dot(lv))
        if lv.get("claimed_cross_product") is not None:
            results.append(verify_vector_cross(lv))
        if lv.get("claimed_angle_deg") is not None:
            results.append(verify_vector_angle(lv))
    if lv.get("vec") is not None and lv.get("claimed_magnitude") is not None:
        results.append(verify_vector_magnitude(lv))
    # Matrices
    if lv.get("mat_a") is not None and lv.get("mat_b") is not None:
        if lv.get("claimed_matrix_sum") is not None:
            results.append(verify_matrix_addition(lv))
        if lv.get("claimed_matrix_product") is not None:
            results.append(verify_matrix_multiplication(lv))
    if lv.get("matrix") is not None:
        if lv.get("claimed_determinant") is not None:
            results.append(verify_matrix_determinant(lv))
        if lv.get("claimed_trace") is not None:
            results.append(verify_matrix_trace(lv))
        if lv.get("claimed_eigenvalues") is not None:
            results.append(verify_matrix_eigenvalues(lv))
        if lv.get("claimed_inverse") is not None:
            results.append(verify_matrix_inverse(lv))
        if lv.get("vec_b") is not None and lv.get("claimed_solution") is not None:
            results.append(verify_linear_system(lv))
    if not results:
        results.append(na("linear_algebra", "no LIN_VERIFY artifacts present"))
    return results
