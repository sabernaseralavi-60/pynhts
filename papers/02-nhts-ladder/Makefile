PY ?= python

.PHONY: all test manuscript clean
all:
	$(PY) run_all.py

manuscript:
	$(PY) run_all.py --manuscript

test:
	$(PY) -m pytest -q

clean:
	rm -f results/tables/v0*.csv results/numbers/*.json results/figures/*
