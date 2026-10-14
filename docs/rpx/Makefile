LATEXMK ?= latexmk
PYTHON ?= python3
KERNEL ?= ../../target/release/rpx
MANUAL := rpx-manual
CHAPTERS := $(wildcard chapters/*.tex)
SPECS := $(wildcard ../*.md)
EXAMPLES := $(wildcard examples/*/*.lp examples/*/*.rpa examples/*/*.json)

.PHONY: all pdf check check-links check-examples clean
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

clean:
	$(LATEXMK) -C -outdir=.build $(MANUAL).tex
