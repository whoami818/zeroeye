.PHONY: install-hooks

install-hooks:
	@echo "🔧 Installing pre-commit hook..."
	@mkdir -p .git/hooks
	@ln -sf ../../tools/pre-commit .git/hooks/pre-commit
	@chmod +x tools/pre-commit
	@echo "✅ Pre-commit hook installed → .git/hooks/pre-commit"

uninstall-hooks:
	@rm -f .git/hooks/pre-commit
	@echo "🗑️  Pre-commit hook removed"
