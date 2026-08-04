#!/usr/bin/env bash
set -euo pipefail

chart_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rendered_digest="$(mktemp)"
rendered_tag="$(mktemp)"
trap 'rm -f "$rendered_digest" "$rendered_tag"' EXIT

source_sha="6e618d0fb5874fa262b783345000f1496e52d7c7"
digest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
repository="registry.digitalocean.com/ragsystemregistry/backend"

helm template nous-dev "$chart_dir" \
  -f "$chart_dir/values.yaml" \
  -f "$chart_dir/values-dev.yaml" \
  --set-string backend.image.tag="$source_sha" \
  --set-string backend.image.sourceSha="$source_sha" \
  --set-string backend.image.digest="$digest" \
  >"$rendered_digest"

digest_image_count="$(
  awk -v image="${repository}@${digest}" \
    '$1 == "image:" && $2 == "\"" image "\"" {count++} END {print count + 0}' \
    "$rendered_digest"
)"
source_annotation_count="$(
  awk -v sha="\"${source_sha}\"" \
    '$1 == "nous-platform.dev/source-sha:" && $2 == sha {count++} END {print count + 0}' \
    "$rendered_digest"
)"

if [[ "$digest_image_count" -ne 5 ]]; then
  echo "expected 5 backend runtime images at ${repository}@${digest}; got ${digest_image_count}" >&2
  exit 1
fi
if [[ "$source_annotation_count" -ne 4 ]]; then
  echo "expected 4 pod-template source annotations; got ${source_annotation_count}" >&2
  exit 1
fi

helm template nous-dev "$chart_dir" \
  -f "$chart_dir/values.yaml" \
  -f "$chart_dir/values-dev.yaml" \
  --set-string backend.image.digest= \
  --set-string backend.image.sourceSha= \
  >"$rendered_tag"

tag="$(awk '$1 == "tag:" {gsub(/\"/, "", $2); print $2; exit}' "$chart_dir/values-dev.yaml")"
tag_image_count="$(
  awk -v image="${repository}:${tag}" \
    '$1 == "image:" && $2 == "\"" image "\"" {count++} END {print count + 0}' \
    "$rendered_tag"
)"
if [[ "$tag_image_count" -ne 5 ]]; then
  echo "expected tag fallback on 5 backend runtime images; got ${tag_image_count}" >&2
  exit 1
fi

if helm template nous-dev "$chart_dir" \
  -f "$chart_dir/values.yaml" \
  -f "$chart_dir/values-dev.yaml" \
  --set-string backend.image.digest=mutable-tag \
  >/dev/null 2>&1; then
  echo "invalid backend digest rendered successfully" >&2
  exit 1
fi
