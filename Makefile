TEXFILES := $(wildcard *.tex) $(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex)
PDFLATEX := pdflatex -interaction=nonstopmode -halt-on-error
ARXIV_ZIP := paper-arXiv.zip
ARXIV_FILES := \
	paper.tex \
	$(wildcard tex/*.tex spec/*.tex spec/*/*.tex paper/*.tex paper/*/*.tex) \
	$(wildcard *.bbl *.bst tex/*.bib)

default: paper.pdf

%.pdf: %.tex $(TEXFILES)
	$(PDFLATEX) $<
	bibtex "$*"
	$(PDFLATEX) $<
	$(PDFLATEX) $<

spec: PurePy-spec.pdf

spec-anon: PurePy-spec-anon.pdf

PurePy-spec-anon.pdf: $(TEXFILES)
	$(PDFLATEX) -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"
	bibtex PurePy-spec-anon
	$(PDFLATEX) -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"
	$(PDFLATEX) -jobname=PurePy-spec-anon "\def\anonmode{}\input{PurePy-spec.tex}"

anon: paper-anon.pdf

paper-anon.pdf: $(TEXFILES)
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	bibtex paper-anon
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"
	$(PDFLATEX) -jobname=paper-anon "\def\anonmode{}\input{paper.tex}"

clean:
	rm -f *.pdf *.aux *.log *.out *.bbl *.blg $(ARXIV_ZIP)

arXiv: $(ARXIV_ZIP)

$(ARXIV_ZIP): $(ARXIV_FILES)
	rm -f $@
	zip -9 $@ $^

.PHONY: default spec spec-anon anon clean arXiv
