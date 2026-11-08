all: jbps
# make         JBPS PDF (main version from 8 Nov 2026)
# make enb      Energy and Buildings PDF (elsarticle)
# make jbps     JBPS PDF (Taylor & Francis Interact)
# make text MD=path/to/manuscript.md   regenerate sections/ from the manuscript
# make clean
enb:
	latexmk -g -pdf -interaction=nonstopmode main-enb.tex
jbps:
	latexmk -g -pdf -interaction=nonstopmode main-jbps.tex
text:
	python3 tools/md_to_tex.py $(MD)
clean:
	latexmk -C main-enb.tex main-jbps.tex
.PHONY: enb jbps text clean
enb11:
	latexmk -g -pdf -interaction=nonstopmode main-enb-11pt.tex
.PHONY: enb11
enb5p:
	latexmk -g -pdf -interaction=nonstopmode main-enb-5p.tex
.PHONY: enb5p
