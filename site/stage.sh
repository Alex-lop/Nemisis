#!/usr/bin/env bash
# Stage the Pages site with the repository's own layout, so the page works the same whether
# GitHub serves the branch directly (.nojekyll) or this staged tree from the workflow:
# index.html at the root, its assets under site/, the banner and the evidence viewer under
# docs/assets/ at the relative paths the viewer was recorded against.
# Usage: bash site/stage.sh <output dir>
set -euo pipefail
out="${1:?output dir}"
rm -rf "$out"
mkdir -p "$out/site" "$out/docs/assets" "$out/benchmarks"
cp index.html .nojekyll "$out/"
cp site/site.css site/kill-field.js site/favicon.svg "$out/site/"
cp docs/assets/nemisis-banner-dark.png "$out/docs/assets/"
cp -R docs/assets/crashcheck-hero "$out/docs/assets/crashcheck-hero"
cp -R benchmarks/results "$out/benchmarks/results"
