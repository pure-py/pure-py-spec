default: language.pdf

%.tex %.v: %.ott
	ott -i $< -o $*.tex -o $*.v

%.pdf: %.tex
	pdflatex $<
	pdflatex $<   # second pass for refs, if needed

clean:
	rm -f *.tex *.v *.pdf *.aux *.log *.out

.PHONY: all clean
