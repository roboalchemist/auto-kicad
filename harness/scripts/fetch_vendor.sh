#!/usr/bin/env bash
# Download the Java 25 runtime and Freerouting jar used by kicad_harness.engine.freerouting
# into harness/.vendor/ (not committed). Freerouting >= 2.2 needs Java 25; macOS's native
# Freerouting CLI build crashes, so the jar is used.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$HERE/.vendor"
FREEROUTING_VERSION="${FREEROUTING_VERSION:-2.5.0}"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64) JRE_ARCH=aarch64 ;;
  x86_64) JRE_ARCH=x64 ;;
  *) echo "unsupported arch $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$VENDOR"

if [ ! -x "$VENDOR/jre/Contents/Home/bin/java" ]; then
  echo "Downloading Temurin JRE 25 ($JRE_ARCH)..."
  tmp="$(mktemp -d)"
  curl -fsSL --max-time 600 -o "$tmp/jre.tar.gz" \
    "https://api.adoptium.net/v3/binary/latest/25/ga/mac/$JRE_ARCH/jre/hotspot/normal/eclipse"
  tar -xzf "$tmp/jre.tar.gz" -C "$tmp"
  rm -rf "$VENDOR/jre"
  mv "$tmp"/jdk-*-jre "$VENDOR/jre"
  rm -rf "$tmp"
fi

if [ ! -f "$VENDOR/freerouting.jar" ]; then
  echo "Downloading Freerouting $FREEROUTING_VERSION..."
  curl -fsSL --max-time 600 -o "$VENDOR/freerouting.jar" \
    "https://github.com/freerouting/freerouting/releases/download/v$FREEROUTING_VERSION/freerouting-$FREEROUTING_VERSION.jar"
fi

"$VENDOR/jre/Contents/Home/bin/java" -version 2>&1 | head -1
ls -l "$VENDOR/freerouting.jar"
