# Contributing to Sandbox Manager

Thank you for contributing! This guide covers how to contribute code, report issues, and manage releases.

## Quick Links

- [Bug Reports](#bug-reports)
- [Feature Requests](#feature-requests)
- [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)

## Bug Reports

**Before reporting:**
- [ ] Search existing [issues](https://github.com/semanticlib/sandbox/issues)
- [ ] Check if fixed in latest version
- [ ] Review logs: `sudo journalctl -u sandbox -f`

**Include in report:**
- Sandbox Manager version
- LXD version (`lxc version`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages (full traceback)
- Screenshots if UI issue

## Feature Requests

**Before requesting:**
- [ ] Search existing [issues](https://github.com/semanticlib/sandbox/issues)
- [ ] Check if it fits project scope (classroom VM management)

**Include in request:**
- Problem you're solving
- Proposed solution
- Alternative solutions considered
- Use case example

## Pull Requests

### Before Submitting

```bash
# Run tests
./scripts/test.sh

# Check code style (if you add new code)
flake8 .

# Update changelog if adding feature/fix
```

### PR Guidelines

1. **One feature/fix per PR** - Keep changes focused
2. **Write tests** - New code needs test coverage
3. **Update documentation** - README, CHANGELOG as needed
4. **Use labels** - For changelog categorization:
   - `feature` - New functionality
   - `bug` - Bug fixes
   - `security` - Security fixes
   - `documentation` - Docs only
   - `tests` - Test additions
   - `chore` - Maintenance

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added (if applicable)

## Checklist
- [ ] Code follows project style
- [ ] Self-review completed
- [ ] Comments added where needed
- [ ] Documentation updated
```

## Development Setup

```bash
# Fork and clone
git clone https://github.com/semanticlib/sandbox.git
cd sandbox

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run tests
./scripts/test.sh
```

## Code Style

- **Python:** PEP 8
- **Commit messages:** Conventional Commits

## Questions?

- Open an [issue](https://github.com/semanticlib/sandbox/issues) for questions
- Check existing issues for answers
- Review [documentation](./README.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
