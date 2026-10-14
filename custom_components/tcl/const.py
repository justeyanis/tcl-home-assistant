"""Constantes pour l'intégration TCL."""

DOMAIN = "tcl"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_MODE = "mode"
CONF_LINE = "line"
CONF_LINE_NAME = "line_name"
CONF_LINE_COLOR = "line_color"
CONF_STATION = "station"
CONF_STOP_IDS = "stop_ids"
CONF_DIRECTION = "direction"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEPARTURE_COUNT = "departure_count"
CONF_SIRI = "realtime_siri"  # temps réel étendu (SIRI estimated-timetables)
CONF_ALERTS = "traffic_alerts"  # alertes trafic de la ligne

DIRECTION_ALL = "__all__"

MODE_METRO = "metro"
MODE_FUNICULAIRE = "funiculaire"
MODE_TRAM = "tram"
MODE_BUS = "bus"

MODES = [MODE_METRO, MODE_FUNICULAIRE, MODE_TRAM, MODE_BUS]

DEFAULT_SCAN_INTERVAL = 60  # secondes
DEFAULT_DEPARTURE_COUNT = 3  # nombre de sensors "Départ #N" par défaut
MAX_DEPARTURE_COUNT = 10
MAX_DEPARTURES_ATTR = 10  # nombre de départs dans l'attribut "departures"


def get_departure_count(entry) -> int:
    """Nombre de départs (= d'entités créées) configuré pour une entrée.

    Les options (modifiables après coup) priment sur la valeur choisie
    lors de la configuration initiale.
    """
    return int(
        entry.options.get(
            CONF_DEPARTURE_COUNT,
            entry.data.get(CONF_DEPARTURE_COUNT, DEFAULT_DEPARTURE_COUNT),
        )
    )

ATTR_DEPARTURES = "departures"
ATTR_STATION = "station"
ATTR_LINE = "ligne"
ATTR_LINE_NAME = "ligne_nom"
ATTR_LINE_COLOR = "couleur"
ATTR_MODE = "mode"
ATTR_DIRECTION = "direction"
ATTR_TCL_BIV = "tcl_biv"
ATTR_ALERTS = "alertes"

# Couleurs officielles du réseau unifié (route_color du GTFS TCL,
# rebranding sept. 2025 : trams tous violets, métro A rose). Fallback si
# l'API ne fournit pas le champ "couleur" ; la couleur de l'API est
# prioritaire.
FALLBACK_COLORS = {
    "A": "#E8308A",
    "B": "#0077C0",
    "C": "#F79727",
    "D": "#009E3D",
    "F1": "#95C23D",
    "F2": "#95C23D",
    "T1": "#863E96",
    "T2": "#863E96",
    "T3": "#863E96",
    "T4": "#863E96",
    "T5": "#863E96",
    "T6": "#863E96",
    "T7": "#863E96",
    "RX": "#B61B29",
}
