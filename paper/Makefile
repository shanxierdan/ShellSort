MAIN ?= main
TECTONIC ?= conda run -n pytorch tectonic

.PHONY: all camera-ready clean

all:
	$(TECTONIC) --keep-logs --keep-intermediates $(MAIN).tex

camera-ready:
	$(MAKE) MAIN=camera-ready

clean:
	$(RM) *.aux *.bbl *.bcf *.blg *.fdb_latexmk *.fls *.log *.out *.run.xml
	$(RM) *.synctex.gz *.toc main.pdf camera-ready.pdf
