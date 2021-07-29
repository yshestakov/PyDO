EPYDOC=./epydoc

html:
	PYTHONPATH=../../src ${EPYDOC} -o html -n pydo -u http://skunkweb.org/pydo.html  ../../src/pydo/

clean:
	-rm -fR html

.PHONY: html clean