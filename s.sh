#!/bin/bash

trap 'echo "[!] Interrupted — killing base.py..."; pkill -f "python3 base.py" 2>/dev/null; exit 1' SIGINT SIGTERM

COUNTRIES=(
  "al" "ar" "am" "au" "at"
  "bs" "be" "ba" "br" "bg"
  "ca" "cl" "co" "cr" "hr"
  "cy" "cz" "dk" "do" "ec"
  "eg" "ee" "fi" "fr" "ge"
  "de" "gr" "hk" "hu" "is"
  "in" "id" "ie" "il" "it"
  "jp" "kz" "ke" "lv" "lt"
  "lu" "my" "mt" "mx" "md"
  "mc" "me" "nl" "nz" "ng"
  "mk" "no" "pk" "pa" "py"
  "pe" "ph" "pl" "pt" "ro"
  "rs" "sg" "sk" "si" "za"
  "kr" "es" "lk" "se" "ch"
  "tw" "th" "tr" "ug" "ua"
  "ae" "gb" "us" "uy" "vn"
  "zm"
)

while true; do
  COUNTRY=${COUNTRIES[$RANDOM % ${#COUNTRIES[@]}]}
  echo "[*] Connecting to NordVPN — $COUNTRY ..."
  nordvpn c "$COUNTRY" 2>/dev/null || nordvpn c 2>/dev/null || true

  sleep 5

  if nordvpn status | grep -qi "Connected"; then
    echo "[+] Connected via $COUNTRY"
  else
    echo "[!] Not connected, retrying..."
    sleep 3
    continue
  fi

  timeout 700 python3 base.py 2>&1; rc=$?
  echo "[*] base.py finished (exit code: $rc) — reconnecting..."
  sleep 3
done
