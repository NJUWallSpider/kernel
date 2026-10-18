LATEXMK ?= latexmk
PYTHON ?= python3
KERNEL ?= ../../target/release/rpx
MANUAL := rpx-manual
CHAPTERS := $(wildcard chapters/*.tex)
SPECS := $(wildcard ../*.md)
EXAMPLES := $(wildcard examples/*/*.lp examples/*/*.rpa examples/*/*.json examples/*/*.py examples/*/*.ipynb)

.PHONY: all pdf check check-links check-examples check-compiler-api clean
all: pdf

pdf: check-links $(MANUAL).pdf

$(MANUAL).pdf: $(MANUAL).tex $(CHAPTERS) $(EXAMPLES) $(SPECS) Makefile
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -file-line-error -outdir=.build $(MANUAL).tex
	cp .build/$(MANUAL).pdf $(MANUAL).pdf

check: pdf check-examples

check-links:
	$(PYTHON) ../../tools/check_docs.py

check-examples:
	$(PYTHON) ../../tools/check_rpx_manual.py --kernel $(KERNEL)

# Requires a built python/rpx/_native.abi3.so.
check-compiler-api:
	$(PYTHON) examples/python-api/elimination.py
	$(PYTHON) examples/python-api/redundant.py
	$(PYTHON) examples/python-api/piecewise.py
	$(PYTHON) examples/python-api/interval_lift.py
	$(PYTHON) examples/python-api/load_models.py

clean:
	$(LATEXMK) -C -outdir=.build $(MANUAL).tex
