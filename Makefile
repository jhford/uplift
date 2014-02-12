.PHONY: test
test:
	chmod +x tests/test_bin/*.sh
	nosetests --rednose

.PHONY: clean
clean:
	find gaia_uplift -name "*.py?" -exec rm {} +
