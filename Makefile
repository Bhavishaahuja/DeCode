PY ?= python

.PHONY: data data-small data-llm data-offline data-test

data:            ## full rebuild of the evidence index + tests
	$(PY) -m data.build

data-small:      ## curated sources only (no OpenAlex discovery)
	$(PY) -m data.build --small

data-llm:        ## full rebuild + claude-sonnet-5 tags for untagged passages
	$(PY) -m data.build --llm

data-offline:    ## rebuild from the data/raw cache only
	$(PY) -m data.build --offline

data-test:
	$(PY) -m data.test_search
