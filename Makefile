PYTHON3 ?= "python3"

gitupdate:
	git submodule init
	git submodule update --recursive

install:
	$(PYTHON3) setup.py develop # yes, develop, not install

test:
	$(PYTHON3) setup.py test # could just run nosetest3...

pypiupload:
	$(PYTHON3) setup.py sdist upload
