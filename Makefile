.PHONY: install build test clean libs services dev-price-monitor dev-trading dev-wallet-tracker dev-tg-bot prod-up prod-down docker-build

DOCKER_EXEC := docker  # podman or docker
VENV_PATH := $(shell pwd)/.venv
PYTHON := $(VENV_PATH)/bin/python
PDM_OPTS := --venv $(VENV_PATH)

# 创建虚拟环境
venv:
	python -m venv $(VENV_PATH)
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install pdm

# 基础设施服务
infra-up:
	$(DOCKER_EXEC) compose up -d mysql redis

infra-down:
	$(DOCKER_EXEC) compose down

# 构建和安装库
libs-install:
	cd libs/common && pdm $(PDM_OPTS) install
	cd libs/cache && pdm $(PDM_OPTS) install
	cd libs/db && pdm $(PDM_OPTS) install
	cd libs/services && pdm $(PDM_OPTS) install
	cd libs/yellowstone_grpc && pdm $(PDM_OPTS) install

libs-build: libs-install
	cd libs/common && pdm $(PDM_OPTS) build
	cd libs/cache && pdm $(PDM_OPTS) build
	cd libs/db && pdm $(PDM_OPTS) build
	cd libs/services && pdm $(PDM_OPTS) build
	cd libs/yellowstone_grpc && pdm $(PDM_OPTS) build

# 构建和安装服务
services-install: libs-install
	cd services/price-monitor && pdm $(PDM_OPTS) install
	cd services/tg-bot && pdm $(PDM_OPTS) install
	cd services/wallet-tracker && pdm $(PDM_OPTS) install
	cd services/trading && pdm $(PDM_OPTS) install

services-build: services-install
	cd services/price-monitor && pdm $(PDM_OPTS) build
	cd services/tg-bot && pdm $(PDM_OPTS) build
	cd services/wallet-tracker && pdm $(PDM_OPTS) build
	cd services/trading && pdm $(PDM_OPTS) build

# 开发环境命令
dev-price-monitor: services-install
	cd services/price-monitor && PYTHONPATH=$(shell pwd)/services/price-monitor/src:$(shell pwd)/libs/*/src $(PYTHON) -m price_monitor

dev-trading: services-install
	cd services/trading && PYTHONPATH=$(shell pwd)/services/trading/src:$(shell pwd)/libs/*/src $(PYTHON) -m trading

dev-wallet-tracker: services-install
	cd services/wallet-tracker && PYTHONPATH=$(shell pwd)/services/wallet-tracker/src:$(shell pwd)/libs/*/src $(PYTHON) -m wallet_tracker

dev-tg-bot: services-install
	cd services/tg-bot && PYTHONPATH=$(shell pwd)/services/tg-bot/src:$(shell pwd)/libs/*/src $(PYTHON) -m tg_bot

# 生产环境命令
prod-up:
	$(DOCKER_EXEC) compose up -d

prod-down:
	$(DOCKER_EXEC) compose down

# 构建所有服务的 Docker 镜像
docker-build:
	$(DOCKER_EXEC) compose build

# 清理
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name "dist" -exec rm -r {} +
	find . -type d -name "build" -exec rm -r {} +
