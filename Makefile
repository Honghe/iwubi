# only really known to work on ubuntu, if you're using anything else, hopefully
# it should at least give you a clue how to install it by hand

PREFIX ?= /usr
SYSCONFDIR ?= /etc
DATADIR ?= $(PREFIX)/share
DESTDIR ?=

PYTHON ?= /usr/bin/python3

install:
	install -m 0755 -d $(DESTDIR)$(DATADIR)/iwubi $(DESTDIR)$(SYSCONFDIR)/xdg/iwubi $(DESTDIR)$(DATADIR)/ibus/component
	install -m 0644 iwubi.svg $(DESTDIR)$(DATADIR)/iwubi
	install -m 0755 iwubi.py $(DESTDIR)$(DATADIR)/iwubi
	install -m 0644 wubi-jidian86.db $(DESTDIR)$(DATADIR)/iwubi
	install -m 0644 config.py $(DESTDIR)$(DATADIR)/iwubi
	install -m 0644 logconfig.py $(DESTDIR)$(DATADIR)/iwubi
	install -m 0644 logconfig.yaml $(DESTDIR)$(DATADIR)/iwubi
	install -m 0644 iwubi.xml $(DESTDIR)$(DATADIR)/ibus/component

uninstall:
	rm -f $(DESTDIR)$(DATADIR)/iwubi/iwubi.svg
	rm -f $(DESTDIR)$(DATADIR)/iwubi/iwubi.py
	rm -f $(DESTDIR)$(DATADIR)/iwubi/wubi-jidian86.db
	rm -f $(DESTDIR)$(DATADIR)/iwubi/config.py
	rm -f $(DESTDIR)$(DATADIR)/iwubi/logconfig.yaml
	rm -f $(DESTDIR)$(DATADIR)/iwubi/logconfig.py
	rmdir $(DESTDIR)$(DATADIR)/iwubi
	rmdir $(DESTDIR)$(SYSCONFDIR)/xdg/iwubi
	rm -f $(DESTDIR)$(DATADIR)/ibus/component/iwubi.xml
