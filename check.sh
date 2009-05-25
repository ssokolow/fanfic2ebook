for X in "$@"; do
	echo "Checking $X..."
	pyflakes "$X" &&
	pychecker -Q --limit=300 "$X" | egrep -v '(scrapers|personalities)\.py:.+ Parameter \((dom|self)\) not used' | egrep -v 'No doc string for function __.+__' &&
	pylint "$X" 2>&1 | grep -v "Unused argument 'dom'" | grep -v "Instance of 'ParseResult' has no 'path' member" | grep -v "Method could be a function" | grep -v "Exception RuntimeError"
done
