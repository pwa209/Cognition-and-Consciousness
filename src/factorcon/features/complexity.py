"""Length-matched neural diversity and complexity summaries."""

from __future__ import annotations

from math import factorial

import numpy as np
from numpy.typing import ArrayLike


def lempel_ziv_binary(sequence: ArrayLike) -> float:
    """Return normalized Lempel-Ziv 1976 complexity of a one-dimensional binary sequence."""

    values = np.asarray(sequence)
    if values.ndim != 1 or len(values) < 4:
        raise ValueError("sequence must be one-dimensional with at least four values")
    if not set(np.unique(values)).issubset({0, 1}):
        raise ValueError("sequence must be binary")
    text = "".join("1" if bool(value) else "0" for value in values)
    dictionary: set[str] = set()
    index = 0
    phrases = 0
    while index < len(text):
        length = 1
        while index + length <= len(text) and text[index : index + length] in dictionary:
            length += 1
        dictionary.add(text[index : min(index + length, len(text))])
        phrases += 1
        index += length
    normalization = len(text) / max(np.log2(len(text)), 1.0)
    return float(phrases / normalization)


def median_binarized_lz(signal: ArrayLike) -> float:
    """Binarize at the sample median and return normalized Lempel-Ziv complexity."""

    values = np.asarray(signal, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("signal must be a finite vector")
    return lempel_ziv_binary(values > np.median(values))


def permutation_entropy(signal: ArrayLike, *, order: int = 3, delay: int = 1) -> float:
    """Return normalized permutation entropy for fixed order and delay."""

    values = np.asarray(signal, dtype=float)
    if values.ndim != 1 or order < 2 or delay < 1:
        raise ValueError("invalid signal, order, or delay")
    count = len(values) - (order - 1) * delay
    if count < 2:
        raise ValueError("signal is too short for requested order and delay")
    patterns: dict[tuple[int, ...], int] = {}
    for index in range(count):
        pattern = tuple(np.argsort(values[index : index + order * delay : delay], kind="stable"))
        patterns[pattern] = patterns.get(pattern, 0) + 1
    probabilities = np.asarray(list(patterns.values()), dtype=float) / count
    entropy = -float(np.sum(probabilities * np.log(probabilities)))
    return entropy / np.log(factorial(order))
