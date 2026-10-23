#!/usr/bin/env bash
# 7 gunden eski tarih klasorlerini siler ve depo gecmisini tek commit'e indirir,
# boylece silinen grafikler GitHub'da yer kaplamaya devam etmez.
# Kullanim: bash tools/temizle.sh /home/claude/kasa-grafik
set -euo pipefail
REPO="${1:-/home/claude/kasa-grafik}"
cd "$REPO"
SINIR=$(TZ=Europe/Istanbul date -d "7 days ago" +%F)
for d in 20??-??-??; do
  [ -d "$d" ] || continue
  if [[ "$d" < "$SINIR" ]]; then
    echo "siliniyor: $d"
    rm -rf "$d"
  fi
done
git checkout -q --orphan temiz
git add -A
git -c user.name="soccermann" -c user.email="umitekici@gmail.com" commit -qm "Grafik arsivi $(TZ=Europe/Istanbul date +%F) (son 7 gun)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git branch -D main >/dev/null 2>&1 || true
git branch -m main
git push -q -f origin main
echo "kalan klasorler:"; ls -d 20??-??-?? 2>/dev/null || true
