# Flavio's PyPI

This repository contains a small toolset for building a static, "dumb" PyPI-style index
from a list of upstream Git repositories. The main entrypoint is `build.sh`, a bash
script that clones repositories, builds wheels, and generates a static package index
using `uv` and `dumb-pypi` tool.

## Features of `build.sh`

- Clones the current repository's `gh-pages` branch into a temporary workspace to
	stage generated index files.
- Iterates over an ordered list of upstream Git repositories, cloning each into a
	temporary directory and invoking `uv build` to produce wheel files.
- Aggregates built wheel files into a temporary `wheels` directory and generates a
	package list used by the index generator.
- Invokes `uv tool run dumb-pypi` to render a static PyPI index (HTML + JSON)
	suitable for serving via any static web server.
- Launches a local HTTP server (Python's `http.server`) bound to `127.0.0.1` for
	quick manual inspection of the generated index.
