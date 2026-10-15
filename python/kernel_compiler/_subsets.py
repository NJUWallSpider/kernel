"""Structural sharing for a caller-supplied bounded-coordinate cancellation.

The author chooses the premise and every desired subset. Removing a term uses
only its declared endpoint. Reusing a containing requested subset and aligned
bound sums changes the derivation DAG, never the mathematical inequality.
"""
from .expr import Expr


def _chunks(indices):
    """Cover supplied coordinates exactly; never scan holes or the model."""
    indices = sorted(indices)
    if not indices:
        return
    start = previous = indices[0]
    for index in indices[1:] + [indices[-1] + 2]:
        if index == previous + 1:
            previous = index
            continue
        end = previous + 1
        while start < end:
            size = (start & -start) if start else 1 << ((end-start).bit_length()-1)
            while size > end-start:
                size //= 2
            yield start, size
            start += size
        start = previous = index


class _BoundSums:
    def __init__(self, builder):
        self.builder = builder
        self.intervals = {}
        self.results = {}

    def live(self, fact):
        from .proof import BuildError
        try:
            self.builder._visible(fact)
        except BuildError:
            return False
        return True

    def interval(self, lower, start, size):
        b = self.builder
        if size == 1:
            return b.lower(start) if lower else b.upper(start)
        key = lower, start, size
        previous = self.intervals.get(key)
        if previous is not None and self.live(previous):
            return previous
        half = size // 2
        result = b.le([(self.interval(lower, start, half), 1),
                       (self.interval(lower, start+half, half), 1)])
        self.intervals[key] = result
        return result

    def cancellation(self, coefficients, removed):
        groups = {}
        for index in removed:
            groups.setdefault(coefficients[index], []).append(index)
        return [(self.interval(coefficient > 0, start, size), abs(coefficient))
                for coefficient, indices in sorted(groups.items())
                for start, size in _chunks(indices)]


def subset_bounds(builder, fact, subsets):
    from .proof import BuildError
    builder._visible(fact)
    if fact.kind not in ("Le", "Eq"):
        raise BuildError("subset_bounds needs a supplied LE or EQ Fact")
    coefficients = fact.expression.terms
    root = frozenset(coefficients)
    requested = []
    for coordinates in subsets:
        if isinstance(coordinates, (str, bytes, Expr)):
            raise BuildError("Each subset must be an iterable of coordinates")
        selected = frozenset(builder.model._index(index) for index in coordinates)
        if not selected <= root:
            raise BuildError("subset_bounds can only retain coordinates in the supplied Fact")
        requested.append(selected)
    if not requested:
        return []

    # Check every needed endpoint before emitting any step. Coordinates retained
    # in all requested subsets need no bound at all.
    common = set(root)
    for selected in requested:
        common.intersection_update(selected)
    for index in root-common:
        variable = builder.model.vars[index]
        lower = coefficients[index] > 0
        if (variable.lower if lower else variable.upper) is None:
            endpoint = "lower" if lower else "upper"
            raise BuildError(f"subset_bounds needs {endpoint} bound for {variable.name!r}")

    cache = getattr(builder, "_subset_bound_sums", None)
    if cache is None:
        cache = builder._subset_bound_sums = _BoundSums(builder)
    root_key = id(fact), root
    cached = cache.results.get(root_key)
    if cached is not None and cached[0] is fact and cache.live(cached[1]):
        root_fact = cached[1]
    else:
        root_fact = fact if fact.kind == "Le" else builder.le([(fact, 1)])
        cache.results[root_key] = fact, root_fact
    known = {root: root_fact}
    for selected in sorted(set(requested), key=lambda s: (-len(s), tuple(sorted(s)))):
        if selected == root:
            continue
        key = id(fact), selected
        cached = cache.results.get(key)
        if cached is not None and cached[0] is fact and cache.live(cached[1]):
            known[selected] = cached[1]
            continue
        # All candidates derive from this same supplied Fact and are themselves
        # caller-requested subsets. This is sharing, not a premise/goal search.
        parent = min((s for s in known if selected <= s), key=len)
        result = builder.le([(known[parent], 1)] + cache.cancellation(coefficients, parent-selected))
        known[selected] = result
        cache.results[key] = fact, result
    return [known[selected] for selected in requested]
