#!/bin/sh
# Single entry point: reuse a suitable runtime, otherwise install a private one.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_prefix=${YUPLUS_INSTALL_PREFIX:-"$HOME/.local/share/yuplus-app"}
selected_python=${YUPLUS_PYTHON:-}
force_managed=false
next=''
for arg in "$@"; do
    if [ "$next" = prefix ]; then install_prefix=$arg; next=''; continue; fi
    if [ "$next" = python ]; then selected_python=$arg; next=''; continue; fi
    case "$arg" in
        --prefix) next=prefix ;;
        --prefix=*) install_prefix=${arg#--prefix=} ;;
        --python) next=python ;;
        --python=*) selected_python=${arg#--python=} ;;
        --managed-python) force_managed=true ;;
    esac
done
case "$install_prefix" in '~/'*) install_prefix="$HOME/${install_prefix#\~/}" ;; esac
suitable() {
    "$1" -c 'import sys,sqlite3; sys.exit(0 if sys.version_info >= (3,12) and sqlite3.sqlite_version_info >= (3,51,3) else 1)' >/dev/null 2>&1
}
if [ -n "$selected_python" ]; then
    exec "$selected_python" "$repo_dir/scripts/install.py" "$@" --python "$selected_python"
fi
if [ "$force_managed" = false ]; then
    for candidate in "$install_prefix/venv/bin/python" python3.14 python3.13 python3.12 python3; do
        if suitable "$candidate"; then
            exec "$candidate" "$repo_dir/scripts/install.py" "$@" --python "$candidate"
        fi
    done
fi
printf '%s\n' 'Yu+: preparing a private Python runtime using the official uv installer.' >&2
mkdir -p "$install_prefix"
install_prefix=$(CDPATH= cd -- "$install_prefix" && pwd)
mkdir -p "$install_prefix/tools" "$install_prefix/python"
if [ ! -x "$install_prefix/tools/uv" ]; then
    staging_dir=$(mktemp -d)
    trap 'rm -rf "$staging_dir"' EXIT HUP INT TERM
    curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh -o "$staging_dir/uv-install.sh"
    UV_INSTALL_DIR="$install_prefix/tools" UV_NO_MODIFY_PATH=1 sh "$staging_dir/uv-install.sh" >&2
    rm -rf "$staging_dir"
    trap - EXIT HUP INT TERM
fi
export UV_PYTHON_INSTALL_DIR="$install_prefix/python"
"$install_prefix/tools/uv" python install --no-bin 3.14 >&2
selected_python=$("$install_prefix/tools/uv" python find --managed-python 3.14)
if ! suitable "$selected_python"; then
    printf '%s\n' 'Downloaded Python does not meet the SQLite >=3.51.3 requirement. No project data was changed.' >&2
    exit 1
fi
exec "$selected_python" "$repo_dir/scripts/install.py" "$@" --python "$selected_python"
