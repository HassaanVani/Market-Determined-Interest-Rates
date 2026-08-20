PYTHON ?= venv/bin/python
V03_SPEC ?= configs/v0.3/main.yaml
V03_CALIBRATION ?= calibration/v0.3/recent_us.json
V03_WORKERS ?= 1

.PHONY: download-data data calibrate pilot pilot-h7 pilot-power smoke freeze-spec confirm llm-robustness llm-assets concentration-freeze concentration-run concentration-assets local-sensitivity-freeze local-sensitivity-run local-sensitivity-assets consolidate verify-consolidation paper-assets robustness-assets release release-verify purge-inventory verify lock

download-data:
	$(PYTHON) -m v03.download_sources

data:
	$(PYTHON) -m v03.cli data

calibrate:
	$(PYTHON) -m v03.calibrate_pipeline

pilot:
	$(PYTHON) -m v03.cli pilot --spec $(V03_SPEC) --calibration $(V03_CALIBRATION) --workers $(V03_WORKERS)

pilot-h7:
	$(PYTHON) -m v03.cli pilot-h7 --spec $(V03_SPEC) --calibration $(V03_CALIBRATION) --workers $(V03_WORKERS)

pilot-power:
	$(PYTHON) -m v03.power
	$(PYTHON) -m v03.h7_pilot_analysis

smoke:
	$(PYTHON) -m v03.cli smoke --spec $(V03_SPEC) --calibration $(V03_CALIBRATION) --workers $(V03_WORKERS)

freeze-spec:
	$(PYTHON) -m v03.cli freeze-spec --spec $(V03_SPEC)

confirm:
	$(PYTHON) -m v03.cli confirm --calibration $(V03_CALIBRATION) --workers $(V03_WORKERS)

llm-robustness:
	$(PYTHON) -m v03.llm_robustness --pairs 30 --model deepseek-r1:8b

llm-assets:
	$(PYTHON) -m v03.llm_assets

concentration-freeze:
	$(PYTHON) -m v03.concentration_addendum freeze

concentration-run:
	$(PYTHON) -m v03.concentration_addendum run --workers $(V03_WORKERS)
	$(PYTHON) -m v03.concentration_addendum consolidate
	$(PYTHON) -m v03.concentration_addendum verify

concentration-assets:
	$(PYTHON) -m v03.concentration_addendum analyze

local-sensitivity-freeze:
	$(PYTHON) -m v03.local_sensitivity freeze

local-sensitivity-run:
	$(PYTHON) -m v03.local_sensitivity run --workers $(V03_WORKERS)
	$(PYTHON) -m v03.local_sensitivity consolidate
	$(PYTHON) -m v03.local_sensitivity verify

local-sensitivity-assets:
	$(PYTHON) -m v03.local_sensitivity analyze

release:
	$(PYTHON) -m v03.release build

release-verify:
	$(PYTHON) -m v03.release verify

purge-inventory:
	$(PYTHON) -m v03.release inventory

consolidate:
	$(PYTHON) -m v03.cli consolidate

verify-consolidation:
	$(PYTHON) -m v03.cli verify-consolidation

paper-assets: consolidate
	$(PYTHON) -m v03.paper_assets
	$(PYTHON) -m v03.llm_assets
	$(PYTHON) -m v03.robustness_assets

robustness-assets:
	$(PYTHON) -m v03.robustness_assets

verify:
	$(PYTHON) -m pytest -q
	$(PYTHON) -m v03.cli verify

lock:
	$(PYTHON) -m v03.environment_lock
