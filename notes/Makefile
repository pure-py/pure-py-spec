SPEC := ..
export TEXINPUTS := .:$(CURDIR)/$(SPEC):
export BIBINPUTS := $(CURDIR)/$(SPEC):
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error

## Draft notes on gradual typing
graduality.pdf: graduality.tex $(wildcard graduality/*.tex graduality/*/*.tex)
	$(MAKE) -C $(SPEC) generated/python-version.tex generated/mypy-version.tex generated/mechanisation-names.tex \
		generated/conformance-counts.tex
	$(PDFLATEX) graduality
	bibtex graduality
	$(PDFLATEX) graduality
	$(PDFLATEX) graduality

clean:
	rm -f *.aux *.bbl *.blg *.cb *.cb2 *.log *.out *.pdf

.PHONY: clean
