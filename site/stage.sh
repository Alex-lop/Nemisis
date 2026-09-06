#!/usr/bin/env bash
# Stage the Pages site: the landing page, the banner it shows, and the evidence viewer at the
# relative path it was recorded against. Usage: bash site/stage.sh <output dir>
set -euo pipefail
out="${1:?output dir}"
rm -rf "$out"
mkdir -p "$out/assets" "$out/docs/assets" "$out/benchmarks"
cp site/index.html site/site.css site/kill-field.js site/favicon.svg "$out/"
cp docs/assets/nemisis-banner-dark.png "$out/assets/"
cp -R docs/assets/crashcheck-hero "$out/docs/assets/crashcheck-hero"
cp -R benchmarks/results "$out/benchmarks/results"
touch "$out/.nojekyll"
