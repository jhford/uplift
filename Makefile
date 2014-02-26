.PHONY: test
test:
	rm -rf .scratch_
	nosetests --rednose

COVERAGE_DIR=coverage
.PHONY: coverage
coverage:
	rm -rf $(COVERAGE_DIR)
	nosetests --with-coverage --cover-package=gaia_uplift --cover-html --cover-html-dir=$(COVERAGE_DIR)
	open $(COVERAGE_DIR)/index.html

.PHONY: release-test
release-test: test
	# This is a more exhaustive set of tests
	# including some real world testing
	@echo Running tests again using distutils driver
	python setup.py test
	@echo Re-doing setup.py develop
	python setup.py develop
	@echo Doing a test uplift show
	yes n | uplift show
	@echo ...And a repository update
	uplift update

.PHONY: clean
clean:
	find gaia_uplift -name "*.py?" -exec rm {} +

.PHONY: release
release: release-test
	@if [ $(git status --porcelain -uno | wc -l) != 0 ] ; then \
		echo "WILL NOT DO A RELEASE ON A DIRTY WORKING COPY" ; \
	fi
	echo $$(( $$(awk "/[0-9]+/ { print $$1 }" < version) + 1)) > version
	git add version
	git commit -m "Relase for v$$(awk "/[0-9]+/ { print $$1 }" < version)"
	git tag "v$$(awk "/[0-9]+/ { print $$1 }" < version)"
	git push origin master "v$$(awk "/[0-9]+/ { print $$1 }" < version)" 
	python setup.py develop
	python setup.py sdist upload

