test:
	nosetests --rednose

clean:
	find gaia_uplift -name "*.py?" -exec rm {} +
