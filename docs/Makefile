LATEXMK ?= latexmk
PYTHON ?= python3
KERNEL ?= ../target/release/rpx
MANUAL := rpx-manual
CHAPTERS := $(wildcard rpx/chapters/*.tex)
EXAMPLES := $(wildcard rpx/examples/*/*.lp rpx/examples/*/*.rpa rpx/examples/*/*.json)

.PHONY: all pdf check-examples clean
all: pdf

pdf: $(MANUAL).pdf

$(MANUAL).pdf: $(MANUAL).tex $(CHAPTERS) $(EXAMPLES)
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -file-line-error -outdir=.build $(MANUAL).tex
	cp .build/$(MANUAL).pdf $(MANUAL).pdf

check-examples:
	$(PYTHON) ../tools/check_rpx_manual.py --kernel $(KERNEL)

clean:
	$(LATEXMK) -C -outdir=.build $(MANUAL).tex
