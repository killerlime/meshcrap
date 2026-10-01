#!/bin/bash
# Run on a disposable native ARM64 Debian/Raspberry Pi OS build host.
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$PWD
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$repo"
test "$(id -u)" = 0 || { echo 'Run on a disposable ARM64 build host as root.'; exit 1; }
test "$(uname -m)" = aarch64 || { echo 'Native ARM64 Linux is required; Windows and x86 builds are not validated.'; exit 1; }
test -z "$(git status --porcelain)" || { echo 'Commit reviewed source changes locally before building.'; exit 1; }
python3 tests/privacy_check.py
revision=4d8ee447dd3d37e8b0ef8752e460d9082d9d435d
work=$(mktemp -d /var/tmp/meshcrap-pigen.XXXXXXXX)
# Retain the work directory for inspection; pi-gen may leave mounts on failure.
echo "Disposable build workspace: $work"
git clone --no-checkout https://github.com/RPi-Distro/pi-gen.git "$work/pi-gen"
git -C "$work/pi-gen" checkout --detach "$revision"
builder="$work/pi-gen"
stage="$builder/stage-meshcrap"
mkdir -p "$stage/00-meshcrap/files" "$repo/dist/pi"
git archive HEAD | gzip > "$stage/00-meshcrap/files/source.tar.gz"
cp deploy/pi/prerun.sh "$stage/prerun.sh"
cp deploy/pi/install.sh "$stage/00-meshcrap/00-run.sh"
chmod +x "$stage/prerun.sh" "$stage/00-meshcrap/00-run.sh"
printf 'python3-venv python3-pip ca-certificates\n' > "$stage/00-meshcrap/00-packages"
printf 'IMG_SUFFIX="-lite"\n' > "$stage/EXPORT_IMAGE"
touch "$builder/stage2/SKIP_IMAGES"
cat > "$builder/config" <<'EOF'
IMG_NAME='meshcrap'
PI_GEN_RELEASE='Meshcrap community image (unofficial)'
RELEASE='trixie'
DEPLOY_COMPRESSION='none'
COMPRESSION_LEVEL=6
TARGET_HOSTNAME='meshcrap'
FIRST_USER_NAME='pi'
ENABLE_SSH=0
PASSWORDLESS_SUDO=0
DISABLE_FIRST_BOOT_USER_RENAME=0
STAGE_LIST='stage0 stage1 stage2 stage-meshcrap'
EOF
# No password, Wi-Fi profile or SSH key is passed into pi-gen.
(cd "$builder"; ./build.sh)
shopt -s nullglob
images=("$builder"/deploy/*meshcrap*.img)
test "${#images[@]}" = 1 || { echo 'Expected one final Pi image'; exit 1; }
bash deploy/pi/verify-image.sh "${images[0]}" "$repo/dist/pi/IMAGE-AUDIT.json"
xz -T2 -6 -c "${images[0]}" > "$repo/dist/pi/meshcrap-arm64.img.xz"
xz -t "$repo/dist/pi/meshcrap-arm64.img.xz"
git archive HEAD | gzip > "$repo/dist/pi/meshcrap-source.tar.gz"
cp deploy/pi/README.md "$repo/dist/pi/README.md"
printf 'Application commit: %s\npi-gen commit: %s\nArchitecture: arm64\nOS: Raspberry Pi OS Lite Trixie\nStatus: build only; physical Pi boot verification required\n' "$(git rev-parse HEAD)" "$revision" > "$repo/dist/pi/BUILD.txt"
(cd "$repo/dist/pi"; sha256sum meshcrap-arm64.img.xz > SHA256SUMS)
echo 'Image created. Do not publish before artifact privacy/license review and physical boot tests.'
