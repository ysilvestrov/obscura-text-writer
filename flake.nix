{
  description = "Obscura Text Writer (Storygen) — неофіційне середовище розробки Nix (Linux / macOS)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
        python = pkgs.python312;

        nativeLibs = with pkgs; [
          zlib
          libxml2
          libxslt
          libjpeg
          freetype
          openssl
          libffi
        ];

        linuxLibraryPath = pkgs.lib.makeLibraryPath (nativeLibs ++ [ pkgs.stdenv.cc.cc.lib ]);

        ensureVenv = pkgs.writeShellScript "obscura-ensure-venv" ''
          set -euo pipefail

          PROJECT_ROOT="$(pwd)"
          EXTRAS="''${1:-web,dev,publication}"

          if [ ! -f "$PROJECT_ROOT/pyproject.toml" ] || [ ! -f "$PROJECT_ROOT/requirements-lock.txt" ]; then
            echo "Помилка: запустіть команду з кореня репозиторію Obscura Text Writer (не знайдено pyproject.toml або requirements-lock.txt у $PROJECT_ROOT)." >&2
            exit 1
          fi

          LOCK_HASH="$(${python}/bin/python3 -c '
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
extras = sys.argv[2]
h = hashlib.sha256()
h.update(extras.encode("utf-8"))
for name in ("requirements-lock.txt", "pyproject.toml"):
    h.update(b"\0")
    h.update(name.encode("utf-8"))
    h.update(b"\0")
    h.update((root / name).read_bytes())
print(h.hexdigest())
' "$PROJECT_ROOT" "$EXTRAS")"

          VENV_DIR="$PROJECT_ROOT/.venv"
          STAMP_FILE="$VENV_DIR/.nix-lock.sha256"

          if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -f "$STAMP_FILE" ] || [ "$(cat "$STAMP_FILE" 2>/dev/null || true)" != "$LOCK_HASH" ]; then
            CREATED_FRESH=0
            if [ ! -d "$VENV_DIR" ]; then
              CREATED_FRESH=1
              echo "==> Створення віртуального середовища Python (.venv)..."
              if ! ${python}/bin/python3 -m venv "$VENV_DIR"; then
                rm -rf "$VENV_DIR"
                exit 1
              fi
            else
              echo "==> Оновлення залежностей у .venv..."
            fi

            cleanup_on_error() {
              if [ "$CREATED_FRESH" -eq 1 ]; then
                rm -rf "$VENV_DIR"
              else
                rm -f "$STAMP_FILE"
              fi
            }

            if ! env -u PYTHONPATH "$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet; then
              cleanup_on_error
              exit 1
            fi
            if ! env -u PYTHONPATH "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_ROOT/requirements-lock.txt" --quiet; then
              cleanup_on_error
              exit 1
            fi
            if ! env -u PYTHONPATH "$VENV_DIR/bin/python" -m pip install --no-deps -e "$PROJECT_ROOT[$EXTRAS]" --quiet; then
              cleanup_on_error
              exit 1
            fi

            printf '%s\n' "$LOCK_HASH" > "$STAMP_FILE"
            echo "==> Середовище .venv успішно підготовлено!"
          fi
        '';
      in
      {
        devShells.default = pkgs.mkShell {
          name = "obscura-dev-shell";

          buildInputs = with pkgs; [
            # Python runtime (includes built-in venv and ensurepip)
            python

            # Node.js toolchain for web frontend and waitlist worker
            nodejs_22
            pnpm

            # System & development utilities
            git
            pkg-config
          ] ++ nativeLibs ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
            pkgs.apple-sdk
          ];

          shellHook = ''
            PROJECT_ROOT="$(pwd)"

            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              if [ -f /etc/NIXOS ]; then
                export LD_LIBRARY_PATH="${linuxLibraryPath}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              fi
            ''}

            if [ -f "$PROJECT_ROOT/pyproject.toml" ] && [ -f "$PROJECT_ROOT/requirements-lock.txt" ]; then
              ${ensureVenv} "web,dev,publication"
            else
              echo "Попередження: pyproject.toml або requirements-lock.txt не знайдено у $PROJECT_ROOT; пропуск ініціалізації .venv." >&2
            fi

            if [ -d "$PROJECT_ROOT/.venv/bin" ]; then
              export PATH="$PROJECT_ROOT/.venv/bin:$PATH"
            fi

            echo "=========================================================="
            echo "  Obscura Text Writer (Storygen) — Nix Dev Environment    "
            echo "  (неофіційне середовище для контриб'юторів)               "
            echo "=========================================================="
            echo "  Python:  $(${python}/bin/python3 --version)"
            echo "  Node.js: $(${pkgs.nodejs_22}/bin/node --version)"
            echo "  pnpm:    $(${pkgs.pnpm}/bin/pnpm --version)"
            echo "=========================================================="
          '';
        };

        apps.default = {
          type = "app";
          program = toString (pkgs.writeShellScript "storygen-run" ''
            set -euo pipefail
            PROJECT_ROOT="$(pwd)"

            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              export LD_LIBRARY_PATH="${linuxLibraryPath}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
            ''}

            ${ensureVenv} "web,publication"
            exec "$PROJECT_ROOT/.venv/bin/python" -m storygen.server "$@"
          '');
        };
      }
    );
}
