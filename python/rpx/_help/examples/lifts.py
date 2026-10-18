"""Self-contained, verified examples for each constructive lift family."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from rpx import (
    ModelBuilder,
    Proof,
    IntervalSpec,
    MenuSpec,
    SignedSpec,
    FlowSpec,
    FlowGroup,
    SubflowSpec,
    SubflowGroup,
)


def build_proof(family):
    b = ModelBuilder(family)
    if family in ("interval", "menu"):
        x = b.add_var("x", integer=True, lower=0, upper=1)
    elif family == "signed":
        f = b.add_var("f", lower=-2, upper=2)
        z = b.add_var("z", integer=True, lower=0, upper=1)
        b.add_row("p", f - 2 * z, upper=0)
        b.add_row("n", -f - 2 * z, upper=0)
    else:
        f = b.add_var("f", lower=2, upper=2)
        if family == "subflow":
            g = b.add_var("g", lower=1, upper=1)
    model = b.build()
    proof = Proof(model, model)
    s = proof.forward
    if family == "interval":
        lift = s.lift_intervals(
            [
                IntervalSpec([0], [x], [s.lower(x)]),
                IntervalSpec(
                    [x, 0],
                    [1, 2],
                    [s.upper(x), s.derive.le(s.upper(x) - 1), None, None],
                ),
            ]
        )
        assert lift[0].upper_rows[0].expression == lift[0].variable - x
        assert len(lift[1].lower_rows) == 2
    elif family == "menu":
        lift = s.lift_menus(
            [
                MenuSpec(
                    1, 1, x, [None, None, None, s.lower(x), s.upper(x), s.integer(x)]
                )
            ]
        )
        a, c = lift[0].options
        assert lift[0].sum.expression == a + c - 1
        assert lift[0].moment.expression == c - x
    elif family == "signed":
        lift = s.lift_signed(
            [
                SignedSpec(
                    2,
                    f,
                    z,
                    [s.lower(z), s.upper(z), s.integer(z), s.row("p"), s.row("n")],
                )
            ]
        )
        item = lift[0]
        assert item.flow.expression == item.positive - item.negative - f
        assert (
            item.activation.expression
            == item.positive_activation + item.negative_activation - z
        )
    elif family == "flow":
        eq = s.derive.eq_on_fixed(f - 2)
        lift = s.lift_flow(
            FlowSpec(
                2,
                [(0, 1)],
                [
                    FlowGroup(
                        0,
                        [(1, 1), (1, 1)],
                        [f],
                        [s.derive.le(s.lower(f) - 2)],
                        [eq, s.derive.eq(-eq)],
                    )
                ],
            )
        )
        item = lift[0]
        assert item.source == 0 and item.commodities[0].demand == 1
        assert (
            item.recovery[0].expression
            == item.commodities[0].flows[0] + item.commodities[1].flows[0] - f
        )
    elif family == "subflow":
        eq = s.derive.eq_on_fixed(f - g - 1)
        lift = s.lift_subflow(
            SubflowSpec(
                2,
                [(0, 1), (1, 0)],
                [
                    SubflowGroup(
                        0,
                        [(1, 1)],
                        [f, g],
                        [s.derive.le(s.lower(f) - 2), s.derive.le(s.lower(g) - 1)],
                        [eq, s.derive.eq(-eq)],
                    )
                ],
            )
        )
        a, c = lift[0].flows
        assert lift[0].balances[0].expression == a - c - 1
        assert lift[0].remainder_nonnegative[0].expression == a - f
    else:
        raise ValueError(family)
    lift.scope.map(default="same_name").finish()
    proof.reverse.map(default="same_name").finish()
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "family",
        choices=("interval", "menu", "signed", "flow", "subflow", "all"),
        nargs="?",
        default="all",
    )
    family = parser.parse_args().family
    families = (
        ("interval", "menu", "signed", "flow", "subflow")
        if family == "all"
        else (family,)
    )
    with TemporaryDirectory() as directory:
        for name in families:
            report = build_proof(name).verify(Path(directory) / name).raise_for_status()
            print(name, report.status)


if __name__ == "__main__":
    main()
