"""Parseur SIRI Lite (estimated-timetables) du réseau TCL.

Le flux `estimated-timetables.json` de data.grandlyon.com donne, pour chaque
course suivie par le SAE (ActIV), l'heure théorique ET l'heure estimée à chacun
des arrêts restants, ainsi que les suppressions. Il complète utilement le
dataset `tclpassagearret`, limité aux 2 prochains passages par ligne/arrêt.

Constats (flux public, 2026) :
  - filtrage serveur par ligne : `?LineRef=ActIV:Line::T2:SYTRAL` ;
  - références : `ActIV:StopArea:SP:32166:SYTRAL` -> arrêt 32166 (même
    numérotation que les points d'arrêt `tclarret`/`tclpassagearret`) ;
  - horodatages en UTC (`Z`), parfois avec 9 décimales ; la valeur
    `0001-01-01T00:00:00Z` signifie « non renseigné » ;
  - disponibilité irrégulière : ce flux n'est jamais bloquant.

Module volontairement sans dépendance à Home Assistant ni aiohttp.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from typing import Any

SIRI_BASE_URL = "https://data.grandlyon.com/siri-lite/2.0"
SIRI_ET_URL = f"{SIRI_BASE_URL}/estimated-timetables.json"
LINE_REF_TEMPLATE = "ActIV:Line::{line}:SYTRAL"

_NAMESPACES = frozenset({"SYTRAL", "LOC", "TCL"})
_LONG_FRACTION = re.compile(r"(\.\d{6})\d+")


def line_ref(line_code: str) -> str:
    """'T2' -> 'ActIV:Line::T2:SYTRAL' (forme exigée par ?LineRef=)."""
    return LINE_REF_TEMPLATE.format(line=line_code.strip().upper())


def parse_ref(ref: str | None) -> str | None:
    """Identifiant utile d'une référence SIRI.

    'ActIV:Line::T2:SYTRAL' -> 'T2', 'ActIV:StopArea:SP:32166:SYTRAL' -> '32166'.
    Une forme inconnue est renvoyée telle quelle.
    """
    if not ref:
        return None
    parts = ref.split(":")
    if len(parts) >= 2 and parts[-1] in _NAMESPACES:
        return parts[-2] or None
    return ref


def parse_time(value: str | None) -> datetime | None:
    """Horodatage SIRI -> datetime aware (None si absent ou sentinelle)."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("0001-01-01"):
        return None
    text = _LONG_FRACTION.sub(r"\1", text)
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _value(node: Any) -> str | None:
    """Déballe le format SIRI {"value": x} (tolère une valeur nue)."""
    if isinstance(node, dict):
        node = node.get("value")
    if node is None:
        return None
    return str(node)


def _as_list(node: Any) -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return [node]
    return []


def _journeys(payload: Any) -> Iterator[dict]:
    siri = payload.get("Siri") if isinstance(payload, dict) else None
    delivery = (siri or {}).get("ServiceDelivery") or {}
    for et in _as_list(delivery.get("EstimatedTimetableDelivery")):
        for frame in _as_list(et.get("EstimatedJourneyVersionFrame")):
            for journey in _as_list(frame.get("EstimatedVehicleJourney")):
                if isinstance(journey, dict):
                    yield journey


def summarize(payload: Any) -> dict:
    """Résumé d'un payload, pour diagnostiquer une absence de passages."""
    journeys = list(_journeys(payload))
    stops: list[str] = []
    for journey in journeys[:3]:
        estimated = journey.get("EstimatedCalls") or {}
        for call in _as_list(estimated.get("EstimatedCall"))[:4]:
            if isinstance(call, dict):
                ref = _value(call.get("StopPointRef"))
                if ref and ref not in stops:
                    stops.append(ref)
    lines = sorted(
        {parse_ref(_value(j.get("LineRef"))) or "?" for j in journeys}
    )
    return {"courses": len(journeys), "lignes": lines[:5], "exemples_arrets": stops[:6]}


def parse_estimated_calls(
    payload: Any, stop_ids: Iterable[str], line_code: str | None = None
) -> list[dict]:
    """Passages aux arrêts demandés, extraits d'un payload estimated-timetables.

    Chaque élément : {ligne, arret, destination_id, sens, course, theorique,
    estime, annule}. `estime` vaut None quand le SAE n'a pas (encore)
    d'estimation pour ce passage : il reste alors purement théorique.
    """
    wanted = {str(s) for s in stop_ids}
    target = line_code.strip().upper() if line_code else None
    calls: list[dict] = []
    for journey in _journeys(payload):
        line = parse_ref(_value(journey.get("LineRef")))
        if target and line and line.upper() != target:
            continue
        framed = journey.get("FramedVehicleJourneyRef") or {}
        course = parse_ref(
            _value(framed.get("DatedVehicleJourneyRef"))
            or _value(journey.get("DatedVehicleJourneyRef"))
        )
        destination_name = _value(
            (_as_list(journey.get("DestinationName")) or [None])[0]
        )
        journey_cancelled = bool(journey.get("Cancellation"))
        estimated = journey.get("EstimatedCalls") or {}
        for call in _as_list(estimated.get("EstimatedCall")):
            if not isinstance(call, dict):
                continue
            stop = parse_ref(_value(call.get("StopPointRef")))
            if stop not in wanted:
                continue
            aimed = parse_time(call.get("AimedDepartureTime")) or parse_time(
                call.get("AimedArrivalTime")
            )
            expected = parse_time(call.get("ExpectedDepartureTime")) or parse_time(
                call.get("ExpectedArrivalTime")
            )
            if aimed is None and expected is None:
                continue
            display = _value(
                (_as_list(call.get("DestinationDisplay")) or [None])[0]
            )
            status = (_value(call.get("DepartureStatus")) or "").lower()
            calls.append(
                {
                    "ligne": line,
                    "arret": stop,
                    "destination_id": parse_ref(
                        _value(journey.get("DestinationRef"))
                    ),
                    "destination_nom": display or destination_name,
                    "sens": _value(journey.get("DirectionRef")),
                    "course": course,
                    "theorique": aimed,
                    "estime": expected,
                    "annule": journey_cancelled
                    or bool(call.get("Cancellation"))
                    or status in ("cancelled", "canceled"),
                }
            )
    calls.sort(key=lambda c: c["estime"] or c["theorique"])
    return calls
