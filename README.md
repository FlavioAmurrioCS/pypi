# Flavio's PyPI

This repository contains a small toolset for building a static, "dumb" PyPI-style index
from a list of upstream Git repositories. The main entrypoint is `build.sh`, a bash
script that clones repositories, builds wheels, and generates a static package index
using `uv` and `dumb-pypi` tool.

## WARNING!
This repo is a proof of concept and should not be used for production. I mainly
made this for writing some PEP723 with some shared library without needing to
have it be published.
[--extra-index-url is unsafe! (intermediate)](https://youtu.be/fWquXVcTKjU)

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

## Installing from this index

### Using environmental variables

To configure most tool you can set the following environmental variables. Add these to your ~/{.bash|.zsh}rc to persist the change.
```bash
export PIP_EXTRA_INDEX_URL="https://flavioamurriocs.github.io/pypi/simple"
export UV_INDEX="https://flavioamurriocs.github.io/pypi/simple"

# To be explicit, you can set the default index as well. If your company uses a mirror, make sure to point to it here.
export PIP_INDEX_URL="https://pypi.org/simple"
export UV_DEFAULT_INDEX="https://pypi.org/simple"
```

### Working with pip

```bash
pip install --extra-index-url=https://flavioamurriocs.github.io/pypi/simple uv-to-pipfile
```

### Working with uv (Recommended)
NOTE: uv tries to address the `dependency confusion` attack by making the dafault-index take priority. ([reference](https://docs.astral.sh/uv/reference/cli/#uv-add--index-strategy))
```bash
uv add --index=https://flavioamurriocs.github.io/pypi/simple uv-to-pipfile
```

If working with a script you can use the following template.

```python
#!/usr/bin/env uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "uv-to-pipfile",
# ]
#
# [[tool.uv.index]]
# url = "https://flavioamurriocs.github.io/pypi/simple"
#
# [[tool.uv.index]]
# url = "https://pypi.org/simple"
# default = true
# ///


def main() -> None:
    print("Hello from main.py!")


if __name__ == "__main__":
    main()
```

### Working with pipenv

You must add this index as a `[[source]]` and then make your package make use of it in its declaration.
For more info check this: https://docs.pipenv.org/advanced/#specifying-package-indexes

```toml
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[[source]]
url = "https://flavioamurriocs.github.io/pypi/simple"
verify_ssl = true
name = "private"

[packages]
requests = "*"
uv-to-pipfile = { version= "*", index="private"}

[dev-packages]

[requires]
python_version = "3.12"
```
