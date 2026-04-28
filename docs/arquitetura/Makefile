PLANTUML ?= java -jar /opt/plantuml/plantuml.jar
PUML := $(wildcard *.puml)
SVG  := $(PUML:.puml=.svg)
PNG  := $(PUML:.puml=.png)

.PHONY: all svg png clean

all: svg png

svg: $(SVG)
png: $(PNG)

%.svg: %.puml
	$(PLANTUML) -tsvg $<

%.png: %.puml
	$(PLANTUML) -tpng $<

clean:
	rm -f *.svg *.png
