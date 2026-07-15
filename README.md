# TCL Lyon pour Home Assistant

[![hacs][hacs-badge]][hacs-link]
[![Ajouter à HACS][hacs-repo-badge]][hacs-repo-link]
[![Version][version-badge]][releases-link]
[![Licence][license-badge]](LICENSE)

Intégration custom **TCL (Transports en Commun Lyonnais)** + carte Lovelace **`tcl-biv-card`** reproduisant les BIV du réseau (écran jaune métro / afficheur LED orange tram-bus).

Inspirée de [droso-hass/idfm](https://github.com/droso-hass/idfm) : ajout via l'interface avec un assistant **mode → ligne → station → direction**.

## Installation en un clic

[![Ouvrir dans HACS][hacs-repo-badge]][hacs-repo-link]

1. **Ajouter le dépôt à HACS** — cliquez sur le bouton ci-dessus (ou dans HACS : ⋮ → *Dépôts personnalisés* → collez `https://github.com/justeyanis/tcl-home-assistant`, catégorie *Intégration*), puis installez **TCL Lyon** et redémarrez Home Assistant.
2. **Ajouter l'intégration** — cliquez sur le bouton ci-dessous, ou **Paramètres → Appareils et services → Ajouter une intégration → « TCL Lyon »**.

   [![Ajouter l'intégration][config-flow-badge]][config-flow-link]

3. Suivre l'assistant : identifiants → mode → ligne → station → direction → nombre de départs.

La carte Lovelace **`tcl-biv-card` est servie et enregistrée automatiquement** par l'intégration : aucune ressource à ajouter à la main, aucun `?v=` à gérer. Elle apparaît directement dans le sélecteur de cartes (« TCL BIV Card »).

## Prérequis : compte data.grandlyon.com

Les passages temps réel TCL (dataset `tcl_sytral.tclpassagearret`) nécessitent une authentification (Basic Auth) :

1. Créer un compte sur [GrandLyon Connect](https://moncompte.grandlyon.com/login/).
2. Définir un mot de passe **pour la plateforme data** via [mot de passe oublié](https://data.grandlyon.com/portail/fr/mot-de-passe-oublie) (en étant déconnecté).
3. Identifiant = votre e-mail, mot de passe = celui défini à l'étape 2.

## L'intégration

Chaque entrée crée un appareil nommé `TCL <ligne> <station> → <direction>` avec **un nombre d'entités au choix** (1 à 10, demandé à la dernière étape de l'assistant) : `#0` (prochain départ), `#1`, `#2`… — par exemple `TCL B Debourg → Charpennes Charles Hernu #0` (état = minutes restantes). L'entité `#0` porte l'attribut `departures` (jusqu'à 10 prochains passages) et le marqueur `tcl_biv: true` utilisé par la carte pour l'auto-découverte.

L'intervalle de rafraîchissement (60 s par défaut) et le nombre de départs se règlent à tout moment dans les options de l'intégration (les entités sont créées/supprimées en conséquence).

**Ajouter un arrêt** sans se ré-authentifier : dès qu'une entrée existe, « Ajouter un service » sur la page de l'intégration réutilise vos identifiants et démarre directement au choix du mode.

## La carte Lovelace

La carte est **servie et enregistrée automatiquement** par l'intégration (ressource `/tcl-biv-card/tcl-biv-card.js`, cache géré tout seul à chaque version). Rien à copier, rien à déclarer. Ajoutez-la depuis le sélecteur de cartes du tableau de bord (**« TCL BIV Card »**) :

```yaml
type: custom:tcl-biv-card
```

> Tableaux de bord en mode **YAML** uniquement : l'auto-enregistrement ne s'applique pas, ajoutez la ressource à la main — `url: /tcl-biv-card/tcl-biv-card.js`, `type: module`.

La carte a un **éditeur graphique 100 % autonome** (cases à cocher pour les entités, tous les réglages visibles — aucune dépendance aux composants internes de HA). Le YAML reste disponible pour les mêmes réglages.

Les **pictogrammes officiels des lignes** (SVG du site tcl.fr : mode + carré couleur de ligne) sont affichés dans le bandeau, avec repli automatique sur une pastille colorée si l'image ne charge pas (`line_icon: official | badge | none`).

Le menu déroulant des stations n'est **jamais affiché** par défaut (une carte = les entités que vous avez choisies) ; remettez-le avec `show_selector: true` si vous voulez une carte multi-stations.

Style métro : bandeau jaune « Direction … » avec pastille verte et picto, grosse horloge verte à gauche, lignes « Prochain : 2 min » oranges. À 0 minute, le **picto clignotant remplace le délai** (comme les vrais BIV). Une alternative 100 % YAML (sans cette carte, via `html-template-card`) est fournie dans [examples/metro-biv-html-template.yaml](examples/metro-biv-html-template.yaml).

Toutes les options YAML :

| Option | Défaut | Rôle |
|---|---|---|
| `entity` / `entities` | auto-découverte | une entité `#0` précise, ou une liste |
| `station` | — | station présélectionnée (auto-découverte) |
| `style` | `auto` | **force le rendu** : `metro` (panneau jaune) ou `tram` (LED orange) |
| `count` | `3` | nombre de départs affichés |
| `title` | — | titre de carte optionnel |
| `show_selector` | `false` | menu déroulant des stations (multi-stations) |
| `show_header` | `true` | bandeau direction |
| `show_clock` / `show_date` | `true` | horloge (écran métro / pied tram) et date (tram) |
| `show_destination` | `true` | colonne destination (style tram uniquement) |
| `show_picto` | `true` | picto véhicule : uniquement quand la rame est à quai, à la place du délai (clignote) |
| `line_icon` | `official` | pictogramme de ligne : `official` (SVG tcl.fr), `badge` (pastille), `none` |
| `header` | direction configurée | texte principal du bandeau |
| `header_prefix` | `Direction` | préfixe du bandeau |
| `via` | — | sous-texte à droite du bandeau, `\n` = saut de ligne |
| `labels` | `[Prochain, Suivant]` | libellés des rangs en style métro (le dernier se répète) |
| `line_color` | couleur de ligne | couleur de la pastille |
| `header_bg` | jaune / gris | fond du bandeau |
| `clock_color` | `#39e639` | horloge (métro) |
| `label_color` | `#ff7a1a` | libellés « Prochain / Suivant » |
| `value_color` | `#3dc473` | délais et picto |
| `led_color` | `#ffa61a` | texte LED (tram) |

Exemple reproduisant le BIV du funiculaire de Vieux Lyon :

```yaml
type: custom:tcl-biv-card
entity: sensor.tcl_f1_vieux_lyon_cat_st_jean_saint_just_0
style: metro
count: 2
header: SAINT-JUST
via: "par Minimes\nThéâtres romains"
```

Sans `style`, le rendu s'adapte au mode : **métro/funiculaire** → panneau jaune + écran noir (grosse horloge verte, Prochain/Suivant, picto clignotant à quai) ; **tram/bus** → afficheur à LED orange avec destination et minutes, date/heure en pied.

Entre deux rafraîchissements de l'API, la carte recalcule les délais côté client à partir de l'heure de passage : un départ disparaît **30 secondes avant son heure réelle**. Toute la carte est en Arial, sans italique, et la direction s'affiche toujours en entier (retour à la ligne si besoin).

## Horaires théoriques (GTFS)

Quand le temps réel est vide (la nuit, ou service terminé), l'intégration complète avec les horaires théoriques du GTFS officiel TCL, téléchargé automatiquement chaque semaine avec vos identifiants (fichier `tcl_gtfs.zip` dans votre dossier de config, ~50-100 Mo). L'index se construit en tâche de fond au premier démarrage : les départs théoriques peuvent mettre quelques minutes à apparaître la première fois. Sur la carte, un départ à plus d'une heure s'affiche « HH:MM » plutôt qu'en minutes.

## Notes techniques

- API : services REST JSON `datapusher` de data.grandlyon.com ([doc](https://rdata-grandlyon.readthedocs.io/fr/latest/services.html)). Filtre serveur `?field=<champ>&value=<valeur>` (les autres syntaxes sont détectées et écartées automatiquement) ; récupération de table complète via `maxfeatures=-1`.
- Les noms de tables (`tcl_sytral.*`, versions incluses) sont **découverts dynamiquement** au démarrage : l'intégration survit aux renommages type "réseau TCL unifié".
- Les noms de champs ont des alias de repli (`ligne`/`code_ligne`, `nom`/`nom_arret`, etc.).
- Tous les horaires (temps réel et GTFS) sont interprétés en heure de Lyon (`Europe/Paris`), quel que soit le fuseau du serveur HA.
- La couleur officielle de ligne vient du champ `couleur` des datasets lignes ; à défaut, palette de secours intégrée (couleurs du réseau unifié 2025).
- Le choix de direction propose les destinations observées en temps réel au moment de la config, complétées par les terminus connus (liste vide la nuit → « Toutes les directions », ou saisie libre).
- La comparaison des directions tolère les **abréviations des girouettes TCL** : « St-Genis-Laval Hôp. Sud » correspond bien à « Saint-Genis-Laval Hôpital Lyon Sud ».

## Dépannage

Si les départs ne s'affichent pas :

1. Activez les logs debug et guettez notamment l'avertissement « Aucun passage ne correspond à la direction configurée » (direction obsolète → reconfigurez l'entrée) :

```yaml
logger:
  logs:
    custom_components.tcl: debug
```

2. Lancez le script de diagnostic (Python 3.9+, aucune dépendance) qui vérifie chaque maillon — station, temps réel, filtre de direction, GTFS :

```bash
python diagnose.py --station "Charpennes" --ligne B --direction "St-Genis"
```

## Licence

[MIT](LICENSE). Ce projet est indépendant : non affilié à SYTRAL Mobilités, TCL ni la Métropole de Lyon. Les pictogrammes de lignes affichés proviennent du site public tcl.fr et restent la propriété de leurs ayants droit.

<!-- Liens & badges -->
[releases-link]: https://github.com/justeyanis/tcl-home-assistant/releases
[version-badge]: https://img.shields.io/github/v/release/justeyanis/tcl-home-assistant?label=version
[license-badge]: https://img.shields.io/github/license/justeyanis/tcl-home-assistant
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-link]: https://github.com/hacs/integration
[hacs-repo-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-repo-link]: https://my.home-assistant.io/redirect/hacs_repository/?owner=justeyanis&repository=tcl-home-assistant&category=integration
[config-flow-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[config-flow-link]: https://my.home-assistant.io/redirect/config_flow_start/?domain=tcl
