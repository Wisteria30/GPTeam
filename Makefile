.PHONY: build install up exec ps down pysen test
#################################################################################
# GLOBALS                                                                       #
#################################################################################

# コンテナ内から実行されたらRUN_CONTEXT変数を空で宣言し、それ以外はコンテナにアクセスする
ifeq ($(IN_CONTAINER), true)
	RUN_CONTEXT :=
else
	RUN_CONTEXT := docker-compose exec gpteam
endif

# 便利
ARG =
#################################################################################
# DOCKER-COMMAND                                                                #
#################################################################################
ps:
	docker-compose ps

build:
	docker-compose build $(ARG)

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

exec:
	docker-compose exec gpteam bash

logs:
	docker-compose logs $(ARG)

build-prod:
	docker-compose -f docker-compose.prod.yml build $(ARG)

up-prod:
	docker-compose -f docker-compose.prod.yml up -d

push-prod:
	docker-compose -f docker-compose.prod.yml push

install:
	$(RUN_CONTEXT) poetry install

install-cpu:
	$(RUN_CONTEXT) poetry install --with cpu

own:
	$(RUN_CONTEXT) poetry install --only-root

#################################################################################
# SCRIPT-COMMANDS                                                               #
#################################################################################
# どう使うかはちょっと検討
DEBUG =-m pdb

.PHONY: run
run:
	gunicorn -c ./gunicorn.conf.py 'main:serve()'

dev:
	$(RUN_CONTEXT) python main.py

index:
	$(RUN_CONTEXT) python scripts/run_indexer.py

pysen:
	-$(RUN_CONTEXT) pysen run lint
	-$(RUN_CONTEXT) pysen run format

test:
	$(RUN_CONTEXT) pytest -v
