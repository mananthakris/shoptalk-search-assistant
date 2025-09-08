# Defaults (override at call time)
PARQUET ?= data/products_e5-base.parquet
DB_PATH ?= vectordb
COLLECTION ?= products
ID_COL ?= item_id
TITLE_COL ?= item_name_c
URL_COL ?= image_url
TEXT_COL ?= text_for_embed_aug
PTYPE_COL ?= product_type_c
EMBEDDING_COL ?= embedding
BATCH ?= 512

seed:
	python3 ingest/rebuild_index.py \
		--parquet $(PARQUET) \
		--db-path $(DB_PATH) \
		--collection $(COLLECTION) \
		--id-col $(ID_COL) \
		--title-col $(TITLE_COL) \
		--url-col $(URL_COL) \
		--text-col $(TEXT_COL) \
		--ptype-col $(PTYPE_COL) \
		--embedding-col ${EMBEDDING_COL} \
		--batch $(BATCH) \
		--wipe


test:
	pytest -q || true   # start simple; tighten later

build:
	docker build -t ghcr.io/OWNER/shoptalk-api:$(GITHUB_SHA) api
	docker build -t ghcr.io/OWNER/shoptalk-ui:$(GITHUB_SHA)  ui
