all: language.tex

language.tex: language.ott
	ott -i language.ott -o language.tex -o language.v

clean:
	rm -f language.tex

.PHONY: all clean
