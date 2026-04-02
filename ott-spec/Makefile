OTT ?= ott
PDFLATEX ?= pdflatex

SRC := language.ott
TEX := language.tex
PDF := language.pdf
COQ := language.v

.PHONY: all coq clean

all: $(PDF)

coq: $(COQ)

$(PDF): $(TEX)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(TEX)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(TEX)

$(TEX): $(SRC)
	$(OTT) -i $(SRC) -o $(TEX)

$(COQ): $(SRC)
	$(OTT) -i $(SRC) -o $(COQ)

clean:
	rm -f $(TEX) $(PDF) $(COQ) *.aux *.log *.out *.toc
