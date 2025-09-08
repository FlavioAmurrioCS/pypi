#!/usr/bin/env uv run --script
# flake8: noqa: E501
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "dev-toolbox",
#     "dumb-pypi",
#     "rich",
#     "typer-slim",
#     "uv",
# ]
# ///
from __future__ import annotations

import glob
import hashlib
import itertools
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import typer
from dev_toolbox.great_value.functional import Stream
from rich.console import Console
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn

if TYPE_CHECKING:
    from typing_extensions import Literal
    from typing_extensions import NotRequired
    from typing_extensions import Self
    from typing_extensions import TypedDict

    class DumbPackage(TypedDict):
        filename: str
        hash: str
        requires_python: str
        core_metadata: NotRequired[Literal["true"]]
        uploaded_by: str
        upload_timestamp: NotRequired[str]
        yanked_reason: NotRequired[str]
        requires_dist: NotRequired[str]


logger = logging.getLogger("private-index")

DEFAULT_BRANCH = "gh-pages"
DEFAULT_WORKDIR = "/tmp/my-repo"
WHEELS_DIRNAME = "wheels"

console = Console()


@dataclass
class Package:
    filename: str
    archive_type: Literal["wheel", "sdist"]
    # version: str

    @classmethod
    def from_file(cls, filename: str) -> Self:
        archive_type = "wheel" if filename.endswith(".whl") else "sdist"

        return cls(
            filename=filename,
            archive_type=archive_type,
        )

    @cached_property
    def requires_python(self) -> str:
        return (
            Stream(self.metadata.splitlines())
            .map(str.strip)
            .filter(lambda x: x.startswith("Requires-Python:"))
            .first()
            .split(":", maxsplit=1)[-1]
            .strip()
        )

    @cached_property
    def metadata(self) -> str:
        metadata_file = f"{self.filename}.metadata"
        if not os.path.exists(metadata_file):
            if self.archive_type == "wheel":
                content = self._extract_from_zip(self.filename)
            else:
                content = self._extract_from_tar(self.filename)
            with open(metadata_file, "w") as f:
                f.write(content)
        else:
            with open(metadata_file) as f:
                content = f.read()

        return content

    @cached_property
    def sha256(self) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(self.filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _extract_from_zip(self, filename: str) -> str:
        with zipfile.ZipFile(filename, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".dist-info/METADATA"):
                    return zf.read(name).decode("utf-8")
        return ""

    def _extract_from_tar(self, filename: str) -> str:
        with tarfile.open(filename, "r:gz") as tf:
            for member in tf.getmembers():
                if member.name.endswith("/METADATA") or member.name.endswith("/PKG-INFO"):
                    return tf.extractfile(member).read().decode("utf-8")
        return ""

    @cached_property
    def dumb_package(self) -> DumbPackage:
        return {
            "filename": os.path.basename(self.filename),
            "hash": f"sha256={self.sha256}",
            "requires_python": self.requires_python,
            "core_metadata": "true",
            "uploaded_by": os.getenv("USER"),
            # "upload_timestamp": "",
            # "yanked_reason": "",
            # "requires_dist": "",
        }


def subprocess_run(
    cmd: tuple[str, ...] | list[str],
    *,
    check: bool = False,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    logger.debug("Command: %s", " ".join(shlex.quote(x) for x in cmd))
    result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)  # noqa: S603
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result


class CLI:
    # repo: str = ""
    # workdir: str = DEFAULT_WORKDIR
    # branch: str = DEFAULT_BRANCH

    def callback(
        self,
        workdir: str | None = None,
        branch: str = DEFAULT_BRANCH,
        repo: str | None = None,
    ) -> None:
        logging.basicConfig(
            level=logging.INFO, format="[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s"
        )
        self.workdir = workdir or DEFAULT_WORKDIR
        self.branch = branch
        self._repo = repo

    @cached_property
    def repo_url(self) -> str:
        if not self._repo:
            cmd = (
                "git",
                "remote",
                "get-url",
                "origin",
            )
            result = subprocess_run(cmd, check=True)
            self._repo = result.stdout.strip()
        return self._repo

    def init_workspace(self) -> None:
        if not os.path.exists(self.workdir):
            cmd = (
                "git",
                "clone",
                "--quiet",
                "--depth=1",
                self.repo_url,
                f"--branch={self.branch}",
                self.workdir,
            )
            subprocess_run(cmd)

    @property
    def wheels_dir(self) -> str:
        return os.path.join(self.workdir, WHEELS_DIRNAME)

    def publish(self) -> None:
        """Commit and push changes to the remote repository."""
        git_cmd = ("git", "-C", self.workdir)
        console.print(f"[bold cyan]📤 Publishing changes to {self.repo_url}[/bold cyan]")
        with suppress(FileNotFoundError):
            shutil.rmtree(os.path.join(self.wheels_dir, ".gitignore"))
        subprocess_run((*git_cmd, "add", self.workdir), check=True)
        subprocess_run((*git_cmd, "commit", "--amend", "--no-edit"), check=True)
        subprocess_run((*git_cmd, "push", "--force"), check=True)
        console.print("[bold green]✅ Published successfully![/bold green]")
        self.clean()

    def serve(self, bind: str = "127.0.0.1", port: int = 8000) -> None:
        """Serve the index using a simple HTTP server."""
        self.init_workspace()
        cmd = (
            sys.executable,
            "-m",
            "http.server",
            f"--bind={bind}",
            f"--directory={self.workdir}",
            f"{port}",
        )
        console.print(f"[bold cyan]🚀 Starting HTTP server on port {port}...[/bold cyan]")
        console.print(f"[bold blue]🌐 Visit: http://127.0.0.1:{port}[/bold blue]")
        subprocess_run(cmd, check=False)

    def add_files(self, files: list[str]) -> None:
        """Add wheel or sdist files to the wheels directory."""
        self.init_workspace()
        for file in files:
            if not file.endswith((".whl", ".tar.gz")):
                logger.warning("The following file cannot be added: %s", file)
                continue
            shutil.copy(file, self.wheels_dir)

    def dumb_packages(self) -> list[DumbPackage]:
        all_files = glob.iglob(os.path.join(self.wheels_dir, "*.whl"))
        tar_gz = glob.iglob(os.path.join(self.wheels_dir, "*.tar.gz"))
        all_files = itertools.chain(all_files, tar_gz)
        return [Package.from_file(x).dumb_package for x in all_files]

    def build(self, title: str = "Flavio's PyPI") -> None:
        """Build the index using dumb-pypi."""
        self.init_workspace()
        for d in ("changelog", "index.html", "packages.json", "pypi", "simple"):
            f = os.path.join(self.workdir, d)
            logger.debug("Removing %s", f)
            with suppress(FileNotFoundError):
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)
        dumb_packages = self.dumb_packages()
        with tempfile.NamedTemporaryFile("w") as f:
            f.writelines((json.dumps(dumb_package) + "\n") for dumb_package in dumb_packages)
            f.flush()
            cmd = (
                "dumb-pypi",
                # "--package-list=${packages_txt}", # path to a list of packages (one per line)
                f"--package-list-json={f.name}",  # path to a list of packages (one JSON object per line)
                # f"--previous-package-list={PREVIOUS_PACKAGES}", # path to the previous list of packages (for partial rebuilds)
                # f"--previous-package-list-json={PREVIOUS_PACKAGES}", # path to the previous list of packages (for partial rebuilds)
                f"--output-dir={self.workdir}",  # path to output to
                f"--packages-url=../../{WHEELS_DIRNAME}/",  # url to packages (can be absolute or relative)
                f"--title={title}",  # site title (for web interface)
                # f"--logo={LOGO}", # URL for logo to display (defaults to no logo)
                # f"--logo-width={LOGO_WIDTH}", # width of logo to display
                "--no-generate-timestamp",  # Don't template creation timestamp in outputs.  This option makes the output repeatable.
                # "--no-per-release-json", # Disable per-release JSON API (/pypi/<package>/<version>/json). This may be useful for large repositories because this metadata can be a huge number of files for little benefit as almost no tools use it.
            )
            subprocess_run(cmd, check=True)
        console.print("[bold green]🏗️  Build complete![/bold green]")

    def clean(self) -> None:
        """Clean the working directory."""
        console.print(f"[bold yellow]🧹 Cleaning workdir: {self.workdir}[/bold yellow]")
        with suppress(FileNotFoundError):
            shutil.rmtree(self.workdir)

    def compile_repositories(self, file: str= "repos.txt") -> None:
        """Build packages from a list of repositories in a file."""
        repos_to_build = (
            Stream.from_io(open(file))  # noqa: SIM115
            .map(str.strip)
            .filter(lambda x: not x.startswith("#"))
            .to_list()
        )
        self.init_workspace()

        console.print(f"[bold cyan]📦 Building {len(repos_to_build)} repositories...[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting builds...", total=len(repos_to_build))

            for repo in repos_to_build:
                # Extract just the repo URL for cleaner display
                repo_url = repo.split()[0].split("/")[-1].replace(".git", "")
                progress.update(task, description=f"Building {repo_url}...")

                with tempfile.TemporaryDirectory() as tmp_repo:
                    try:
                        repo_parts = repo.split()
                        clone_cmd = ("git", "clone", "--quiet", "--depth=1", *repo_parts, tmp_repo)

                        subprocess_run(clone_cmd, check=True)

                        build_cmd = (
                            "uv",
                            "build",
                            "--quiet",
                            tmp_repo,
                            f"--out-dir={self.wheels_dir}",
                        )
                        subprocess_run(
                            build_cmd,
                            check=True,
                        )

                        progress.update(task, description=f"[bold green]✅ Built {repo_url}[/bold green]")

                    except subprocess.CalledProcessError:
                        progress.update(task, description=f"[bold red]❌ Failed {repo_url}[/bold red]")

                progress.advance(task)

            progress.update(task, description="[bold green]🎉 All builds complete![/bold green]")

        console.print(f"[bold green]✅ Successfully processed {len(repos_to_build)} repositories![/bold green]")

    def get_app(self) -> typer.Typer:
        app = typer.Typer(help="Private PyPI index management tool.")
        app.callback()(self.callback)
        app.command()(self.clean)
        app.command()(self.add_files)
        app.command()(self.build)
        app.command()(self.compile_repositories)
        app.command()(self.serve)
        app.command()(self.publish)
        return app


cli = CLI()
app = cli.get_app()

if __name__ == "__main__":
    app()
    # cli.callback()
    # cli.build()
