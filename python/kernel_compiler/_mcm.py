"""Bounded streaming readback of already Kernel-validated frozen MCM v1.

The native reader remains the admission authority. This private decoder avoids
an export-model JSON file and its complete string/list/object representation;
it constructs the existing Python model objects directly from canonical bytes.
"""
from __future__ import annotations

from fractions import Fraction
import os
from pathlib import Path
import struct

from .expr import Expr


BUFFER_BYTES = 1 << 16
# api.MAX_INPUT_BYTES is tighter than codec.MAX_FILE_BYTES (1 GiB).
MAX_INPUT_BYTES = 512 * 1024 * 1024
MAX_ITEMS = 10_000_000
MAX_TOTAL_ITEMS = 20_000_000
MAX_INTEGER_BYTES = 1700
MAX_NAME_BYTES = 1024
MAX_VARS = MAX_ROWS = 2_000_000
MAX_TERMS = 20_000_000
_UINTS = {n: struct.Struct(fmt) for n, fmt in ((1, '<B'), (2, '<H'), (4, '<I'), (8, '<Q'))}
_TAG = struct.Struct('<BBH')
_LENGTHS = struct.Struct('<II')


def _invalid(message):
    raise ValueError(f"INVALID MCM streaming readback: {message}")


def _resource(message):
    raise ValueError(f"RESOURCE_LIMIT MCM streaming readback: {message}")


class _Reader:
    def __init__(self, stream):
        self.stream = stream
        self.size = os.fstat(stream.fileno()).st_size
        if self.size > MAX_INPUT_BYTES:
            _resource("input file byte limit")
        self.position = self.items = self.terms = 0
        if self.take(4) != b"MCM\0":
            _invalid("magic")
        if self.uint(2) != 1:
            _invalid("unsupported version")
        if self.uint(2):
            _invalid("header reserved flags")
        if self.uint(8) != self.size:
            _invalid("file length")

    def take(self, count):
        if count < 0 or count > BUFFER_BYTES:
            _resource("single read buffer limit")
        if self.position + count > self.size:
            _invalid("truncated payload")
        value = self.stream.read(count)
        if len(value) != count:
            _invalid("truncated payload")
        self.position += count
        return value

    def uint(self, size):
        return _UINTS[size].unpack(self.take(size))[0]

    def count(self, minimum_bytes):
        count = self.uint(4)
        self.items += count
        if count > MAX_ITEMS or self.items > MAX_TOTAL_ITEMS:
            _resource("item count limit")
        if count > (self.size-self.position)//minimum_bytes:
            _invalid("count exceeds available payload")
        return count

    def name(self):
        count = self.uint(4)
        if count > MAX_NAME_BYTES:
            _resource("name budget")
        value = self.take(count)
        if not value or not value.isascii() or any(c < 32 or c == 127 for c in value):
            _invalid("empty, non-ASCII, or control-character name")
        return value.decode("ascii")

    def tag(self):
        tag, flag, reserved = _TAG.unpack(self.take(4))
        if flag or reserved:
            _invalid("record reserved flags")
        return tag

    def q(self):
        sign = self.tag()
        if sign > 1:
            _invalid("rational sign")
        nsize, dsize = _LENGTHS.unpack(self.take(8))
        if nsize > MAX_INTEGER_BYTES or dsize > MAX_INTEGER_BYTES:
            _resource("rational magnitude limit")
        if not dsize:
            _invalid("zero denominator length")
        numerator, denominator = self.take(nsize), self.take(dsize)
        if (nsize and not numerator[-1]) or not denominator[-1]:
            _invalid("nonminimal magnitude")
        if not nsize and (sign or denominator != b"\1"):
            _invalid("noncanonical zero")
        n = int.from_bytes(numerator, "little")
        if sign:
            n = -n
        d = int.from_bytes(denominator, "little")
        value = Fraction(n, d)
        if value.numerator != n or value.denominator != d:
            _invalid("unreduced rational")
        return value

    def optional_q(self):
        tag = self.uint(1)
        if tag > 1:
            _invalid("optional rational tag")
        return self.q() if tag else None

    def expression(self, variables):
        constant, count = self.q(), self.count(17)
        self.terms += count
        if self.terms > MAX_TERMS:
            _resource("model term budget")
        def terms():
            previous = -1
            for _ in range(count):
                index, value = self.uint(4), self.q()
                if index <= previous or not value:
                    _invalid("noncanonical expression terms")
                if index >= variables:
                    _invalid("expression coordinate outside model")
                previous = index
                yield index, value
        return Expr(constant, terms())

    def finish(self):
        if self.position != self.size or self.stream.read(1):
            _invalid("trailing bytes")


def read_model(path, model_type, kernel):
    """Construct a Model from one validated snapshot using bounded reads only."""
    from .model import Row, Variable
    path = Path(path)
    with path.open("rb", buffering=BUFFER_BYTES) as stream:
        reader = _Reader(stream)
        name, variable_count = reader.name(), reader.count(10)
        if variable_count > MAX_VARS:
            _resource("model dimension budget")
        variables = []
        for _ in range(variable_count):
            variable_name, domain = reader.name(), reader.tag()
            if domain > 1:
                _invalid("variable domain tag")
            variables.append(Variable(variable_name, bool(domain), reader.optional_q(), reader.optional_q()))
        row_count = reader.count(23)
        if row_count > MAX_ROWS:
            _resource("model dimension budget")
        rows = []
        for _ in range(row_count):
            rows.append(Row(reader.name(), reader.expression(variable_count), reader.optional_q(), reader.optional_q()))
        objective = reader.expression(variable_count)
        reader.finish()
    return model_type(name, variables, rows, objective, kernel=kernel, path=path)
