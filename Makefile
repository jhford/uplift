.PHONY: test
test:
	rm -rf .scratch_
	chmod +x tests/test_bin/*.sh
	nosetests --rednose

.PHONY: clean
clean:
	find gaia_uplift -name "*.py?" -exec rm {} +
