# Default target
all: language.pdf

# Step 1: OTT generates LaTeX (and Coq)
language.tex language.v: language.ott
	ott -i language.ott -o language.tex -o language.v

# Step 2: LaTeX generates PDF
language.pdf: language.tex
	pdflatex language.tex
	pdflatex language.tex   # second pass for refs, if needed

clean:
	rm -f language.tex language.v language.pdf *.aux *.log *.out

.PHONY: all clean
