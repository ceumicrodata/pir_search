build: clean
	python build.py

clean:
	[ -d .git ]
	git clean -Xdf
