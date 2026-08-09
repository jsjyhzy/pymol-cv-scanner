PYTHON ?= python3
VERSION := $(shell sed -n 's/^# Version: //p' src/__init__.py)
PKG     := distance_scan_plugin
DIST    := dist
ARCHIVE := $(DIST)/$(PKG)-$(VERSION).tar.gz
SRC     := $(shell find src -type f)

.PHONY: all dist check test test-pymol clean

all: dist

dist: $(ARCHIVE)

$(ARCHIVE): $(SRC) Makefile
	rm -rf $(DIST)/staging
	mkdir -p $(DIST)/staging
	cp -r src $(DIST)/staging/$(PKG)
	find $(DIST)/staging/$(PKG) -name __pycache__ -type d -prune -exec rm -rf {} +
	find $(DIST)/staging/$(PKG) -name '*.pyc' -delete
	tar -C $(DIST)/staging -czf $@ $(PKG)
	rm -rf $(DIST)/staging

check:
	$(PYTHON) -m py_compile src/*.py scripts/test_plugin_load.py

test: dist
	$(PYTHON) scripts/test_plugin_load.py $(ARCHIVE)

test-pymol: dist
	pymol -cq scripts/test_plugin_load.py -- $(ARCHIVE)

clean:
	rm -rf $(DIST)
