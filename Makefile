.PHONY: test
test:
	rm -rf .scratch_
	nosetests --rednose

.PHONY: clean
clean:
	find gaia_uplift -name "*.py?" -exec rm {} +
