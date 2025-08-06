.PHONY: install build test clean dev-deps infra-up infra-down up down

DOCKER_EXEC := docker  # podman or docker
PKG_MANAGER := conda  # conda or uv

# 安装开发依赖
dev-deps:
ifeq ($(PKG_MANAGER),uv)
	uv sync
else
	conda env update -f environment.yml
endif

# 基础设施服务
infra-up:
	$(DOCKER_EXEC) compose up -d mysql redis

infra-down:
	$(DOCKER_EXEC) compose down

# 主要安装命令
install: dev-deps infra-up
	@echo "🚀 项目初始化完成！"
	@echo "💡 提示："
	@echo "1. 使用 'make up' 启动所有服务"
	@echo "2. 使用 'make down' 停止所有服务"

# Docker 相关命令
build:
	$(DOCKER_EXEC) compose build

up:
	$(DOCKER_EXEC) compose up -d

down:
	$(DOCKER_EXEC) compose down -v

# 清理
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".coverage*" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +
	find . -type d -name "dist" -exec rm -r {} +
	find . -type d -name "build" -exec rm -r {} +
	find . -type d -name ".eggs" -exec rm -r {} +

update-version:
	uv run python scripts/update-version.py

pre-commit-check:
	uv run pre-commit run --all-files | cat
