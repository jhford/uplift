.PHONY: test
test:
	rm -rf .scratch_
	nosetests --rednose

.PHONY: clean
clean:
	find gaia_uplift -name "*.py?" -exec rm {} +

.PHONY: release
release:
	@if [ $(git status --porcelain -uno | wc -l) != 0 ] ; then \
		echo "WILL NOT DO A RELEASE ON A DIRTY WORKING COPY" ; \
	fi
	echo $(( $(awk "/[0-9]+/ { print $1 }" < version) + 1)) > version
	git add version
	git tag "v$(cat version)"
	git commit -m "Relase for version $(cat version)"

