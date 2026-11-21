ifeq ($(wildcard tools/board.mk),)
$(error tools/ is empty: run git submodule update --init)
endif
include tools/board.mk
