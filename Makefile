default: language.pdf

%.pdf: %.tex
	latexmk -pdf $<

clean:
	latexmk -C
	rm -f *.pdf

.PHONY: default clean
