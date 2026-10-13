LATEXMK ?= latexmk
MANUAL := rpx-manual
CHAPTERS := $(wildcard rpx/chapters/*.tex)

.PHONY: all pdf clean
all: pdf

pdf: $(MANUAL).pdf

$(MANUAL).pdf: $(MANUAL).tex $(CHAPTERS)
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -file-line-error -outdir=.build $(MANUAL).tex
	cp .build/$(MANUAL).pdf $(MANUAL).pdf

clean:
	$(LATEXMK) -C -outdir=.build $(MANUAL).tex
