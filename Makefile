# from: https://github.com/fpgmaas/cookiecutter-poetry/blob/main/%7B%7Bcookiecutter.project_name%7D%7D/Makefile

.PHONY: default
default: help ;

.PHONY: shell
shell: install ## Enter project's virtual environment using poetry
	@echo "🚀 Entering project's virtual environment using poetry"
	@poetry shell

.PHONY: install
install: ## Install project using poetry
	@echo "🚀 Installing project using poetry"
	@poetry install

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	@poetry run pytest --doctest-modules

.PHONY: build
build: clean-build ## Build wheel file using poetry
	@echo "🚀 Creating wheel file"
	@poetry build

.PHONY: clean-build
clean-build: ## clean build artifacts
	@rm -rf dist

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
