OTT ?= ott
PDFLATEX ?= pdflatex

OTT_TEX_FLAGS ?= -tex_wrap false

SRC := language.ott
TEX := language.tex
PDF := language.pdf
COQ := language.v

.PHONY: all coq clean

default: $(TEX)

all: $(PDF)

coq: $(COQ)

$(PDF): $(TEX)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(TEX)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(TEX)

$(TEX): $(SRC)
	$(OTT) $(OTT_TEX_FLAGS) -i $(SRC) -o $(TEX)

$(COQ): $(SRC)
	$(OTT) -i $(SRC) -o $(COQ)

ott-preview:
	ott $(SRC) -o $(TEX) -tex_show_meta false
	$(PDFLATEX) -interaction=nonstopmode $(TEX) 

clean:
	rm -f $(TEX) $(PDF) $(COQ) *.aux *.log *.out *.toc
