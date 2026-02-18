default: language.pdf

%.pdf: %.tex
	pdflatex $<
	pdflatex $<   # second pass for refs, if needed

clean:
	rm -f *.pdf *.aux *.log *.out

.PHONY: all clean
