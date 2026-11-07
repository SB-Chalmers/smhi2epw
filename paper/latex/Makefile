# make enb      Energy and Buildings PDF (elsarticle)
# make jbps     JBPS PDF (needs interact.cls, see main-jbps.tex)
# make text MD=path/to/manuscript.md   regenerate sections/ from the manuscript
# make clean
enb:
	latexmk -pdf -interaction=nonstopmode main-enb.tex
jbps:
	latexmk -pdf -interaction=nonstopmode main-jbps.tex
text:
	python3 tools/md_to_tex.py $(MD)
clean:
	latexmk -C main-enb.tex main-jbps.tex
.PHONY: enb jbps text clean
