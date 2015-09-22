build: clean
	pip install -r requirements.txt --no-compile --target .
	zip -r pir-search.pyz petl org_name_search data __main__.py

clean:
	git clean -xdf
