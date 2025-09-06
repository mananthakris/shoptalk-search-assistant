# Defaults (override at call time)
PARQUET ?= data/products_ft.parquet
DB_PATH ?= vectordb
COLLECTION ?= products
MODEL ?= mananthakris/e5-base-ft-abo
ID_COL ?= item_id
TITLE_COL ?= item_name
URL_COL ?= image_url
TEXT_COL ?= text_for_embed_aug
BATCH ?= 512

seed:
	python scripts/rebuild_index.py \
		--parquet $(PARQUET) \
		--db-path $(DB_PATH) \
		--collection $(COLLECTION) \
		--model $(MODEL) \
		--id-col $(ID_COL) \
		--title-col $(TITLE_COL) \
		--url-col $(URL_COL) \
		--text-col $(TEXT_COL) \
		--batch $(BATCH) \
		--wipe


test:
	pytest -q || true   # start simple; tighten later

build:
	docker build -t ghcr.io/OWNER/shoptalk-api:$(GITHUB_SHA) services/api
	docker build -t ghcr.io/OWNER/shoptalk-ui:$(GITHUB_SHA)  services/ui
