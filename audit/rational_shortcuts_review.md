# Independent review of the bounded rational shortcuts prototype

Reviewed `bench/rational-shortcuts-prototype/source.diff`, hash `c2d0188ab9281ac074cec67871fb810b659470afff52084e599d63dd909bb418`,
together with its modified source context, `audit/rational_shortcuts_audit.rs`
and the independent Python Fraction/gcd oracle generator. This is a read-only
review of the prototype; it does not authorize or describe production deployment.
No mathematical or resource-soundness issue was found in these changes.

The denominator-one canonicality shortcut executes only after numerator and
denominator bit checks. A positive denominator one is already reduced for every
BigInt numerator, including zero and negative integers. Negative, zero, oversized
and unreduced other denominators still take the existing checks.

The public expression scaling method validates the full expression and scale
before its zero or unit shortcuts. Multiplication by one is an exact clone;
multiplication by negative one negates only the numerator. Both preserve canonical
form and bit length, and every produced rational is checked as before. Ordering,
allocation bounds and term indices are unchanged.

For the sparse accumulator, a vacant result equals its separately checked product;
there is no omitted nontrivial sum. Occupied entries still check the product before
addition and the result after addition, including overflow before a later exact
cancellation. Constant-zero shortcuts follow the same sequence of checks. Exact
zero entries are removed. This private helper retains its prior assumption that
incoming expressions have been validated by its callers; the change does not
create a new public path around expression validation.

The proposed independent vectors exercise both signs, zero, general fractions,
unit multipliers, cancellation, empty/occupied entries, malformed raw rationals
and the 65,536-bit boundaries. This review did not rerun the owner’s test suite or
measure performance; those results are tracked separately. Tests and this review
are evidence, not a machine-checked proof of the entire implementation.
