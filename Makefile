build: clean dev-env
	mkdir build
	zip -r build/pir-search.pyz petl org_name_search data __main__.py
	./make_exe.py build/pir-search.pyz

clean:
	[ -d .git ]
	git clean -xdf

dev-env:
	pip install -r requirements.txt --no-compile --target .
