#!/usr/bin/env bash
# render.sh — turn a diagram into a PNG so the agent that drew it can look at it.
#
#   render.sh <input.mmd|input.svg> <output.png> [width] [height]
#
# The PNG is evidence, not content: the lesson keeps the mermaid source (or
# embeds the .svg), which Obsidian renders itself. Nothing to install: the
# system Chrome/Chromium does the drawing, mermaid.js is vendored in vendor/.
#
# Exit 3 means no browser was found: the diagram can still go in the lesson,
# marked as not verified.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MERMAID="$ROOT/vendor/mermaid.min.js"

[ $# -ge 2 ] || { echo "usage: $(basename "$0") <input.mmd|input.svg> <output.png> [width] [height]" >&2; exit 2; }
SRC="$1"; OUT="$2"; W="${3:-1200}"; H="${4:-900}"
[ -f "$SRC" ] || { echo "error: no such file: $SRC" >&2; exit 1; }

find_chrome() {
  [ -n "${CHROME:-}" ] && [ -x "$CHROME" ] && { echo "$CHROME"; return; }
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    command -v "$c" 2>/dev/null && return
  done
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
}
CHROME="$(find_chrome || true)"
[ -n "$CHROME" ] || { echo "error: no Chrome or Chromium (set \$CHROME)" >&2; exit 3; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Both kinds are scaled to fill the frame, proportions kept, so small details
# are large enough to inspect.
case "$SRC" in
  *.svg)
    cp "$SRC" "$WORK/fig.svg"
    printf '<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#fff;width:100%%;height:100%%;overflow:hidden}
img{width:100vw;height:100vh;object-fit:contain;box-sizing:border-box;padding:24px}
</style></head><body><img src="fig.svg"></body></html>' > "$WORK/d.html"
    ;;
  *)
    [ -f "$MERMAID" ] || { echo "error: vendor/mermaid.min.js is missing" >&2; exit 1; }
    {
      printf '<!doctype html><html><head><meta charset="utf-8"><script src="%s"></script><style>\n' "$MERMAID"
      printf 'html,body{margin:0;background:#fff;width:100%%;height:100%%;overflow:hidden}\n'
      printf '#d{margin:0;width:100vw;height:100vh;box-sizing:border-box;padding:24px;display:flex;align-items:center;justify-content:center}\n'
      printf '#d svg{width:100%%!important;height:100%%!important;max-width:none!important}\n'
      printf '</style></head><body><pre id="d" class="mermaid">'
      # The source goes in as HTML text, never into JS: labels carry quotes.
      sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$SRC"
      printf '</pre><script>mermaid.initialize({startOnLoad:true,theme:"default"});</script></body></html>'
    } > "$WORK/d.html"
    ;;
esac

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

# Headless Chrome writes the screenshot and then hangs instead of exiting.
# So: start it in the background, wait until the PNG stops growing, kill it.
"$CHROME" --headless --disable-gpu --no-sandbox --no-first-run \
  --user-data-dir="$WORK/profile" --hide-scrollbars --force-device-scale-factor=2 \
  --allow-file-access-from-files --virtual-time-budget=8000 \
  --screenshot="$OUT" --window-size="$W,$H" \
  "file://$WORK/d.html" >/dev/null 2>"$WORK/err.log" &
CPID=$!

SIZE=0
for _ in $(seq 1 100); do
  if [ -s "$OUT" ]; then
    NEW=$(wc -c < "$OUT" 2>/dev/null || echo 0)
    [ "$NEW" = "$SIZE" ] && break
    SIZE="$NEW"
  fi
  kill -0 "$CPID" 2>/dev/null || break
  sleep 0.2
done
kill -9 "$CPID" 2>/dev/null || true
wait "$CPID" 2>/dev/null || true

[ -s "$OUT" ] || { echo "error: no screenshot" >&2; sed -n '1,8p' "$WORK/err.log" >&2; exit 1; }

# A broken diagram still renders — as an error box, or as nothing. Only
# looking at the PNG tells; that look is the whole point of this script.
echo "$OUT (${W}×${H})"
