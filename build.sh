#!/usr/bin/env bash

TITLE="Flavio's PyPI"
BRANCH="gh-pages"
THIS_REPO="$(git remote get-url origin)"

REPOS=(
    "git@github.com:FlavioAmurrioCS/aws-http-auth.git               --branch=main"
    "git@github.com:FlavioAmurrioCS/comma-cli.git                   --branch=cookiecutter"
    "git@github.com:FlavioAmurrioCS/depsdev.git                     --branch=main"
    "git@github.com:FlavioAmurrioCS/dev-toolbox.git                 --branch=main"
    "git@github.com:FlavioAmurrioCS/direct-deps.git                 --branch=main"
    "git@github.com:FlavioAmurrioCS/lambda-dev-server.git           --branch=main"
    "git@github.com:FlavioAmurrioCS/log-tool.git                    --branch=main"
    "git@github.com:FlavioAmurrioCS/persistent-cache-decorator.git  --branch=main"
    "git@github.com:FlavioAmurrioCS/record-replay-compare.git       --branch=main"
    "git@github.com:FlavioAmurrioCS/ripgrep.git                     --branch=master"
    "git@github.com:FlavioAmurrioCS/runtool.git                     --branch=main"
    "git@github.com:FlavioAmurrioCS/typedfzf.git                    --branch=main"
    "git@github.com:FlavioAmurrioCS/uv-to-pipfile.git               --branch=2025.08.02"
    "git@github.com:FlavioAmurrioCS/workflows.git                   --branch=main"
    # "git@github.com:FlavioAmurrioCS/agg.git                         --branch=maturin"
    # "git@github.com:FlavioAmurrioCS/hatch-include.git               --branch=main"
    # "git@github.com:FlavioAmurrioCS/k6.git                          --branch=publish"
    # "git@github.com:FlavioAmurrioCS/lambda-multitool.git            --branch=init"
    # "git@github.com:FlavioAmurrioCS/sshp.git                        --branch=python"
)

function banner(){
    echo "###############################################################################"
    echo "# ${*}"
    echo "###############################################################################"
}

function main(){

    local workdir tmp_repo repo
    workdir="$(mktemp -d)"
    local wheel_dir_basename="wheels"
    local wheeldir="${workdir}/${wheel_dir_basename}"
    # local packages_txt="${workdir}/my-packages.txt"
    local packages_json="${workdir}/my-packages.json"

    git clone --quiet --depth=1 "${THIS_REPO}" -b "${BRANCH}" "${workdir}"

    # shellcheck disable=SC2086
    for repo in "${REPOS[@]}"; do
        echo "- Building ${repo}" &&
        tmp_repo="$(mktemp -d)" &&
        git clone --quiet --depth=1 ${repo} "${tmp_repo}" &&
        uv build --quiet "${tmp_repo}" --out-dir "${wheeldir}" ||
        echo "[ERROR] UNABLE TO BUILD ${repo}"
        rm -rf "${tmp_repo}"
    done

    echo
    banner "Packages"
    rm "${wheeldir}/.gitignore"
    # shellcheck disable=SC2012
    # ls "${wheeldir}" | sort | tee "${packages_txt}"
    local file full_file_path requires_python
    # shellcheck disable=SC2012
    for file in $(ls "${wheeldir}" | sort); do
        full_file_path="${wheeldir}/${file}"

        if [[ "${file}" == *.whl ]]; then
            requires_python="$(unzip -p "${full_file_path}" '*.dist-info/METADATA' | grep '^Requires-Python:' | cut -d' ' -f2)"
        fi
        if [[ "${file}" == *.tar.gz ]]; then
            requires_python="$(tar -xOzf "${full_file_path}" '*/PKG-INFO' | grep '^Requires-Python:' | cut -d' ' -f2)"
        fi

        echo -n '{'
        echo -n "'filename': '${file}', "
        echo -n "'hash': 'sha256=$(sha256 -q "${full_file_path}")', "
        echo -n "'requires_python': '${requires_python}',"
        echo -n "'core_metadata': 'true', "
        echo -n "'uploaded_by': '${USER}'"
        # echo -n "'upload_timestamp': '${}',"
        # echo -n "'yanked_reason': '${}',"
        # echo -n "'requires_dist': '${}',"
        echo '}'
    done | tr "'" '"' | tee "${packages_json}"

    echo

    local dumb_pypi_cmd=(
        uv tool run dumb-pypi
        # "--package-list=${packages_txt}" # path to a list of packages (one per line)
        "--package-list-json=${packages_json}" # path to a list of packages (one JSON object per line)
        # --previous-package-list PREVIOUS_PACKAGES # path to the previous list of packages (for partial rebuilds)
        # --previous-package-list-json PREVIOUS_PACKAGES # path to the previous list of packages (for partial rebuilds)
        "--output-dir=${workdir}" # path to output to
        "--packages-url=../../${wheel_dir_basename}/" # url to packages (can be absolute or relative)
        "--title=${TITLE}" # site title (for web interface)
        # --logo LOGO # URL for logo to display (defaults to no logo)
        # --logo-width LOGO_WIDTH # width of logo to display
        --no-generate-timestamp # Don't template creation timestamp in outputs.  This option makes the output repeatable.
        # --no-per-release-json # Disable per-release JSON API (/pypi/<package>/<version>/json). This may be useful for large repositories because this metadata can be a huge number of files for little benefit as almost no tools use it.
    )

    "${dumb_pypi_cmd[@]}"

    git -C "${workdir}" add "${workdir}"
    git -C "${workdir}" commit --amend --no-edit
    git -C "${workdir}" push --force

    echo "workdir:  ${workdir}"
    echo "wheeldir: ${wheeldir}"
    echo "tmp_repo: ${tmp_repo}"

    python3 -m http.server "--directory=${workdir}" "--bind=127.0.0.1"
    rm -rf "${workdir}"
}

main "${@}"
