build: clean
	mkdir build
	pip install -r requirements.txt --no-compile --target .
	zip -r build/pir-search.pyz petl org_name_search data __main__.py
	./make_exe.py build/pir-search.pyz

clean:
	git clean -xdf
