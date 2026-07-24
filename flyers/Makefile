SHELL := /bin/sh

LATEXMK ?= latexmk
PDFINFO ?= pdfinfo
PDFTOPPM ?= pdftoppm
MAGICK ?= magick
TEX := commons_qr_flyers.tex
ROOT := ..
OUTDIR := $(ROOT)/output/pdf
PDF := $(OUTDIR)/commons_qr_flyers.pdf
CHECK_PREFIX := $(OUTDIR)/.commons_qr_flyers_check
QRS := \
	$(ROOT)/qrs/ph_commons.png \
	$(ROOT)/qrs/ph_mapping.png \
	$(ROOT)/qrs/protohackapp.png

.PHONY: all check clean rebuild

all: $(PDF)

$(PDF): $(TEX) $(QRS)
	mkdir -p $(OUTDIR)
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error \
		-outdir=$(OUTDIR) $(TEX)

rebuild:
	mkdir -p $(OUTDIR)
	$(LATEXMK) -gg -xelatex -interaction=nonstopmode -halt-on-error \
		-outdir=$(OUTDIR) $(TEX)

check: $(PDF)
	test "$$($(PDFINFO) $(PDF) | awk '/^Pages:/ {print $$2}')" = "10"
	$(PDFTOPPM) -f 1 -singlefile -png -r 72 $(PDF) $(CHECK_PREFIX)
	test "$$($(MAGICK) identify -format '%[fx:mean<0.98]' \
		$(CHECK_PREFIX).png)" = "1"
	rm -f $(CHECK_PREFIX).png

clean:
	$(LATEXMK) -c -outdir=$(OUTDIR) $(TEX)
