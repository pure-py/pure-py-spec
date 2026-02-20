TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex fig/*.tex)

default: language.pdf

%.pdf: %.tex $(TEXFILES)
	pdflatex $<
	pdflatex $<   # second pass for refs

clean:
	rm -f *.pdf *.aux *.log *.out

.PHONY: default clean
