# Contributing to heatsweep

Thanks for your interest in contributing. This guide covers the basics.

## Reporting bugs and requesting features

Open an issue on [GitHub Issues](https://github.com/jonelay/heat-sweep/issues).
Include enough detail to reproduce the problem — device TOML, operating
point, and the full traceback if there is one.

## Development setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jonelay/heat-sweep.git
cd heat-sweep
uv sync --extra test
```

For the full development environment including viz:

```bash
uv sync --extra dev
```

## Running tests

```bash
uv run pytest -m "not slow" --tb=short -q
```

## Linting and type checking

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and
import sorting, and [mypy](https://mypy-lang.org/) for type checking.
CI gates on both — check before submitting:

```bash
uv run ruff check heatsweep/ tests/
uv run mypy heatsweep
```

Auto-fix safe lint violations:

```bash
uv run ruff check --fix heatsweep/ tests/
```

## Submitting changes

1. Open an issue first for anything beyond a small bug fix — this avoids
   wasted effort on changes that don't fit the project's direction.
2. Fork the repo and create a branch from `main`.
3. Make your changes, add or update tests as needed.
4. Ensure `uv run ruff check heatsweep/ tests/`,
   `uv run mypy heatsweep`, and `uv run pytest` all pass.
5. Open a pull request against `main`.

Keep PRs focused — one logical change per PR.

## AI-assisted development

Contributors may use AI tools provided they review, understand, and accept
responsibility for the resulting contribution. Material assistance should be
disclosed in the pull-request description or with a non-authorship commit
trailer, which records tool use without assigning authorship:

```text
Assisted-by: <tool>
```

## Scope

heatsweep is a power-electronics thermal design toolkit — semiconductor loss
models and lumped thermal networks. Contributions that extend these
capabilities — bug fixes, new device datasets, documentation improvements,
and performance work — are welcome.

Large-scope additions (new solver backends, integration with other
tools) should start as an issue discussion before any code is written.

## License

This project is licensed under the [Apache License 2.0](LICENSE).
By contributing you agree that your contributions are licensed under
the same terms.
