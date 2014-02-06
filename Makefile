test:
	chmod +x tests/test_bin/*.sh
	nosetests --rednose

clean:
	find gaia_uplift -name "*.py?" -exec rm {} +
