#!/usr/bin/env python3
"""Diagnostic de l'intégration TCL : vérifie chaque maillon de la chaîne.

Usage :
    python diagnose.py --station "Charpennes" --ligne B
    python diagnose.py --station "Charpennes" --ligne B --direction "St-Genis"

Le script demande vos identifiants data.grandlyon.com (jamais stockés) et :
  1. cherche la station dans le dataset public des arrêts ;
  2. interroge le temps réel (tclpassagearret) pour ces arrêts ;
  3. affiche les passages bruts et évalue votre filtre de direction ;
  4. vérifie l'accès au GTFS théorique.

Aucune dépendance : uniquement la bibliothèque standard Python 3.9+.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://data.grandlyon.com/fr/datapusher/ws/rdata"
GTFS_URL = (
    "https://download.data.grandlyon.com/files/rdata/"
    "tcl_sytral.tcltheorique/GTFS_TCL.ZIP"
)

# --- même logique de correspondance que l'intégration -----------------------
_ABBREVIATIONS = {
    "st": "saint",
    "ste": "sainte",
    "hop": "hopital",
    "cat": "cathedrale",
    "princ": "principale",
    "gde": "grande",
}


def norm(value) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c if c.isalnum() else " " for c in text.casefold())
    return " ".join(text.split())


def tokens(value) -> tuple:
    return tuple(_ABBREVIATIONS.get(t, t) for t in norm(value).split())


def fuzzy_match(a, b) -> bool:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    sa, sb = " ".join(ta), " ".join(tb)
    if sa in sb or sb in sa:
        return True
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return set(small) <= set(big)


# --- HTTP --------------------------------------------------------------------
def get_json(url: str, params: dict | None = None, auth: str | None = None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if auth:
        req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", required=True, help="Nom (partiel) de la station")
    parser.add_argument("--ligne", required=True, help="Code de la ligne (B, T1, C3…)")
    parser.add_argument("--direction", help="Direction configurée dans HA (optionnel)")
    parser.add_argument("--username", help="E-mail data.grandlyon.com")
    args = parser.parse_args()

    print("== 1. Recherche de la station (dataset public tclarret) ==")
    data = get_json(f"{BASE}/tcl_sytral.tclarret/all.json", {"maxfeatures": -1})
    stops = data.get("values", [])
    print(f"   {len(stops)} arrêts au total")
    target_line = args.ligne.strip().upper()
    matches = []
    for stop in stops:
        if not fuzzy_match(args.station, stop.get("nom", "")):
            continue
        served = [
            t.split(":")[0].strip().upper()
            for t in str(stop.get("desserte", "")).split(",")
        ]
        if target_line in served:
            matches.append(stop)
    if not matches:
        print(f"   AUCUN arrêt '{args.station}' desservi par {target_line}.")
        print("   Arrêts homonymes trouvés (toutes lignes) :")
        for stop in stops:
            if fuzzy_match(args.station, stop.get("nom", "")):
                print(f"     id={stop['id']} {stop['nom']} desserte={stop['desserte']}")
        return 1
    stop_ids = [str(s["id"]) for s in matches]
    for stop in matches:
        print(f"   id={stop['id']} {stop['nom']} desserte={stop['desserte']}")

    username = args.username or input("E-mail data.grandlyon.com : ")
    password = getpass.getpass("Mot de passe (non affiché) : ")
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()

    print("\n== 2. Passages temps réel (tclpassagearret, authentifié) ==")
    rows = []
    for stop_id in stop_ids:
        try:
            data = get_json(
                f"{BASE}/tcl_sytral.tclpassagearret/all.json",
                {"maxfeatures": 100, "field": "id", "value": stop_id},
                auth,
            )
        except urllib.error.HTTPError as err:
            print(f"   ERREUR HTTP {err.code} : {err.read()[:200]}")
            if err.code in (401, 403):
                print(
                    "   -> Identifiants refusés ou dataset non souscrit : "
                    "connectez-vous sur data.grandlyon.com et vérifiez votre "
                    "accès au jeu de données 'Prochains passages'."
                )
            return 1
        rows.extend(data.get("values", []))
    print(f"   {len(rows)} passages bruts aux arrêts {stop_ids}")
    for row in rows:
        print(
            f"     ligne={row.get('ligne')!r} direction={row.get('direction')!r} "
            f"delai={row.get('delaipassage')!r} heure={row.get('heurepassage')!r} "
            f"type={row.get('type')!r}"
        )

    line_rows = [
        r for r in rows if str(r.get("ligne", "")).strip().upper() == target_line
    ]
    print(f"   dont {len(line_rows)} sur la ligne {target_line}")

    if args.direction:
        print(f"\n== 3. Test du filtre de direction '{args.direction}' ==")
        kept = [
            r for r in line_rows if fuzzy_match(args.direction, r.get("direction", ""))
        ]
        for row in line_rows:
            ok = fuzzy_match(args.direction, row.get("direction", ""))
            print(f"     {'✔' if ok else '✘'} {row.get('direction')!r}")
        if not kept and line_rows:
            print(
                "   -> PROBLÈME : la direction configurée ne correspond à aucun "
                "passage. Reconfigurez l'entrée avec une des directions ci-dessus."
            )

    print("\n== 4. Accès au GTFS théorique ==")
    req = urllib.request.Request(GTFS_URL, method="HEAD")
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            size = int(resp.headers.get("Content-Length", 0)) / 1e6
            print(f"   OK (HTTP {resp.status}, {size:.0f} Mo)")
    except urllib.error.HTTPError as err:
        print(f"   ERREUR HTTP {err.code} : le repli théorique ne fonctionnera pas.")

    print("\nDiagnostic terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
