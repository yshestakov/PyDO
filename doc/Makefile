RST2HTML=/usr/bin/rst2html.py
RST2LATEX=/usr/bin/rst2latex.py
PDFLATEX=/usr/bin/pdflatex
HTMLSTYLESHEET=style.css
HTMLOPTS=-s --footnote-references=brackets
FILENAME=manual

${FILENAME}.html: ${FILENAME}.rst
	${RST2HTML} ${HTMLOPTS} --stylesheet=${HTMLSTYLESHEET} ${FILENAME}.rst ${FILENAME}.html

${FILENAME}.tex: ${FILENAME}.rst
	${RST2LATEX} ${FILENAME}.rst ${FILENAME}.tex

${FILENAME}.pdf: ${FILENAME}.tex
	${PDFLATEX} ${FILENAME}.tex

clean:
	-rm *.html *.tex *.out *.log *.aux *.pdf
