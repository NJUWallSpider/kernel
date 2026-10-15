"""Bounded inspection of the caller's Request, without planning or proof search."""
from itertools import islice

from .expr import Expr, _metadata_rational, _rational_text


def _scalar(value):
    if value is None:
        return None
    value = _metadata_rational(value)
    numerator_bits = abs(value.numerator).bit_length()
    denominator_bits = value.denominator.bit_length()
    if max(numerator_bits, denominator_bits) <= 256:
        return _rational_text(value)
    return {"sign": (value > 0)-(value < 0), "numerator_bits": numerator_bits,
            "denominator_bits": denominator_bits}


def _expression(value, limit):
    if isinstance(value, Expr):
        return value.summary(max_terms=limit)
    terms = value.get("terms", ())
    sample = [[index, _scalar(coefficient)] for index, coefficient in islice(terms, limit)]
    return {"constant": _scalar(value.get("constant", 0)), "term_count": len(terms),
            "terms": sample, "omitted_terms": len(terms)-len(sample)}


def _coordinate(model, index):
    if type(index) is int and 0 <= index < len(model.vars):
        return model.vars[index].name
    # Raw Request authoring still reaches Kernel's own INVALID diagnostic.
    return {"index": index, "error": "invalid_coordinate"}


def summarize_request(source, target, request, *, max_items=8):
    """Describe explicit contracts; the complete Request remains authoritative.

    At most ``max_items`` entries are shown in each collection. This never
    serializes maps, asks Kernel for obligations, or infers a stronger relation.
    A summary is inspection metadata and is not a verification result.
    """
    if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 0:
        raise ValueError("max_items must be a nonnegative integer")
    if isinstance(request, (list, tuple)):
        request = {"claims": request}
    counts = {key: len(request.get(key, ())) for key in ("claims", "points", "improvements", "bijections")}
    result = {"counts": counts, "models": {"source": source.stats(), "target": target.stats()},
              "note": "Caller-declared scope only; Kernel verifies the complete Request. Each directional claim requires a total map and all output feasibility obligations."}
    claims = []
    for index, claim in enumerate(islice(request.get("claims", ()), max_items)):
        inp, out = (target, source) if claim["reverse"] else (source, target)
        projection = claim.get("projection", ())
        affine = claim.get("affine_projection", ())
        restrictions = {}
        if claim.get("input_objective_level") is not None:
            restrictions["objective_level"] = _scalar(claim["input_objective_level"])
        if claim.get("input_halfspace") is not None:
            restrictions["halfspace"] = _expression(claim["input_halfspace"], max_items)
        pairs = [{"input": _coordinate(inp, i), "output": _coordinate(out, j)}
                 for i, j in islice(projection, max_items)]
        observations = {"coordinate_count": len(projection), "coordinates": pairs,
                        "omitted_coordinates": len(projection)-len(pairs), "affine_count": len(affine)}
        observations["affine"] = [{"input": _expression(a, max_items), "output": _expression(b, max_items)}
                                   for a, b in islice(affine, max_items)]
        observations["omitted_affine"] = len(affine)-len(observations["affine"])
        claims.append({"index": index, "direction": "target_to_source" if claim["reverse"] else "source_to_target",
                       "input_integers": claim["input_integers"], "output_integers": claim["output_integers"],
                       "objective": claim["objective"], "inverse_claim": claim.get("inverse"),
                       "input_restrictions": restrictions,
                       "input_objective_lower": _scalar(claim.get("input_objective_lower")),
                       "input_objective_lower_scope": "declared_input_domain" if claim.get("input_objective_lower") is not None else None,
                       "observations": observations})
    result["claims"] = claims
    result["omitted_claims"] = counts["claims"]-len(claims)
    points = []
    for index, point in enumerate(islice(request.get("points", ()), max_items)):
        kind, contract = next(iter(point.items()))
        item = {"index": index, "kind": kind}
        if kind == "Feasible":
            item.update(target=contract["target"], integers=contract["integers"],
                        objective=_scalar(contract.get("objective")))
        elif kind in ("Strictness", "FiberStrictness"):
            item["inclusion_claim"] = contract["inclusion_claim"]
        elif kind == "ImageExclusion":
            item.update(point_in_target=contract["point_in_target"], map_coordinates=len(contract["map"]))
        points.append(item)
    result["points"] = points
    improvements = []
    for index, contract in enumerate(islice(request.get("improvements", ()), max_items)):
        improvements.append({"index": index, "target": contract["target"], "integers": contract["integers"],
                             "positive": _expression(contract["positive"], max_items)})
    result["improvements"] = improvements
    result["bijections"] = [{"index": index, "forward_claim": contract["forward_claim"],
                             "reverse_claim": contract["reverse_claim"]}
                            for index, contract in enumerate(islice(request.get("bijections", ()), max_items))]
    for key in ("points", "improvements", "bijections"):
        result["omitted_"+key] = counts[key]-len(result[key])
    return result
