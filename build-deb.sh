#!/bin/sh
# Build gói .deb vào dist/. Chỉ cần dpkg-deb (có sẵn trên Ubuntu), không cần sudo.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$DIR/rgbctl/__init__.py")"
[ -n "$VERSION" ] || { echo "Không đọc được version trong rgbctl/__init__.py" >&2; exit 1; }

BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
ROOT="$BUILD/rgbctl_$VERSION"
P="$DIR/packaging"

install -d "$ROOT/DEBIAN" "$ROOT/usr/lib/rgbctl/rgbctl"
install -m 644 "$DIR"/rgbctl/*.py "$ROOT/usr/lib/rgbctl/rgbctl/"
install -D -m 755 "$P/rgbctl" "$ROOT/usr/bin/rgbctl"
install -D -m 644 "$P/60-rgbctl.rules" "$ROOT/usr/lib/udev/rules.d/60-rgbctl.rules"
install -D -m 644 "$P/rgbctl.conf" "$ROOT/usr/lib/modules-load.d/rgbctl.conf"
install -D -m 644 "$P/rgbctl-daemon.service" "$ROOT/usr/lib/systemd/user/rgbctl-daemon.service"
install -D -m 644 "$P/dev.hoan.rgbctl.desktop" "$ROOT/usr/share/applications/dev.hoan.rgbctl.desktop"
install -D -m 644 "$P/rgbctl-tray.desktop" "$ROOT/etc/xdg/autostart/rgbctl-tray.desktop"
install -D -m 644 "$DIR/icons/rgbctl.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/rgbctl.svg"
install -D -m 644 "$DIR/icons/rgbctl-symbolic.svg" \
    "$ROOT/usr/share/icons/hicolor/symbolic/apps/rgbctl-symbolic.svg"
install -D -m 644 "$DIR/README.md" "$ROOT/usr/share/doc/rgbctl/README.md"

# umask của máy build có thể để thư mục 775; gói nên luôn là 755
find "$ROOT" -type d -exec chmod 755 {} +
SIZE="$(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" "$P/control.in" > "$ROOT/DEBIAN/control"
install -m 755 "$P/postinst" "$P/prerm" "$P/postrm" "$ROOT/DEBIAN/"
echo /etc/xdg/autostart/rgbctl-tray.desktop > "$ROOT/DEBIAN/conffiles"

mkdir -p "$DIR/dist"
OUT="$DIR/dist/rgbctl_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT" >/dev/null
echo "$OUT"
