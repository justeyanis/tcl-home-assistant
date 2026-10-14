# TCL Lyon pour Home Assistant

[![hacs][hacs-badge]][hacs-link]
[![Ajouter à HACS][hacs-repo-badge]][hacs-repo-link]
[![Version][version-badge]][releases-link]
[![Licence][license-badge]](LICENSE)

Intégration custom **TCL (Transports en Commun Lyonnais)** + carte Lovelace **`tcl-biv-card`** reproduisant les BIV du réseau (écran jaune métro / afficheur LED orange tram-bus).

- **Temps réel** des métros, trams et bus, avec **retards** (+3 min) et **passages supprimés** quand le SAE TCL les publie ;
- **Alertes trafic** de la ligne : capteur « Perturbation » + bandeau défilant sur la carte ;
- **Horaires théoriques** en complément (la nuit, fin de service) ;
- carte fidèle aux panneaux TCL, adaptée au mobile et à la vue « sections ».

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

Chaque appareil comporte aussi :

| Entité | Rôle |
|---|---|
| `… Prochain départ` | **horodatage** du prochain passage (idéal pour les automatisations et l'affichage « à 18:42 ») |
| `… Perturbation` (binaire) | allumé tant qu'une **perturbation** est en cours sur la ligne (les simples « Information » sont listées sans l'allumer) ; attributs `titre`, `nombre`, `alertes` |

Attributs utiles des entités `#N` : `destination`, `heure`, `heure_theorique`, `retard` (minutes, si connu), `temps_reel` (estimation SAE ou simple horaire), `source` (`siri`, `tcl` ou `gtfs`). Un passage **supprimé** n'est jamais compté comme « prochain départ » mais reste visible sur la carte.

Dans les **options** de l'intégration (⚙ sur l'entrée), à tout moment :

- **changer la direction** sans supprimer/recréer l'entrée (liste des terminus observés + horaires théoriques, ou saisie libre) ;
- intervalle de rafraîchissement (60 s par défaut) et nombre de départs (les entités sont créées/supprimées en conséquence) ;
- activer/désactiver le **temps réel étendu** (flux SIRI) et les **alertes trafic**.

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
| `show_realtime` | `true` | pastille « ondes » sur les passages suivis en temps réel ; horaires purement théoriques atténués |
| `show_delay` | `true` | badge de retard (`+3`) et passages **SUPPRIMÉ** barrés |
| `show_alerts` | `true` | bandeau des alertes trafic : étiquette colorée selon la gravité (info / travaux / perturbation / majeure) + texte défilant ; **un clic le déplie** (cause, période « du … au … », message complet) |
| `show_approach` | `true` | tram/bus suivis en temps réel : « À L'APPROCHE » (< 2 min 30) puis « À QUAI » (< 1 min) avec le picto du véhicule (Citadis pour le tram, bus de face pour le bus) |
| `show_line` | `auto` | badge de ligne sur chaque rangée : `auto` (si plusieurs lignes), `true`, `false` |
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

« À l'approche » et « à quai » sont déduits de l'heure estimée par le SAE TCL (comme sur les BIV) : aucune donnée publique ne signale physiquement la présence d'un véhicule à quai, ni la composition des rames (simple ou unité multiple sur le métro B).

Pratique au quotidien :

- **un clic** sur le panneau ouvre le détail de l'entité (historique, attributs) ; un clic sur le bandeau d'alertes en affiche le détail ;
- **plusieurs lignes au même arrêt** (ex. `entities: [sensor.tcl_c3_cordeliers_0, sensor.tcl_c13_cordeliers_0]`) : les départs sont fusionnés et chaque rangée porte le badge de sa ligne ;
- la carte se **réduit automatiquement** sur mobile / colonnes étroites et occupe toute la largeur en vue « sections » ;
- les animations (défilement, clignotement) respectent le réglage système « réduire les animations ».

### Exemples d'automatisations

Prévenir s'il faut partir (le prochain tram est dans 6 minutes) :

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.tcl_t1_debourg_iut_feyssine_0
    below: 7
conditions:
  - condition: time
    after: "07:30:00"
    before: "08:30:00"
    weekday: [mon, tue, wed, thu, fri]
actions:
  - action: notify.mobile_app_mon_telephone
    data:
      message: >
        T1 dans {{ states('sensor.tcl_t1_debourg_iut_feyssine_0') }} min
        {% if state_attr('sensor.tcl_t1_debourg_iut_feyssine_0', 'retard') %}
        (retard +{{ state_attr('sensor.tcl_t1_debourg_iut_feyssine_0', 'retard') }} min)
        {% endif %}
```

Être alerté d'une perturbation sur sa ligne :

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.tcl_b_debourg_charpennes_charles_hernu_perturbation
    to: "on"
actions:
  - action: notify.mobile_app_mon_telephone
    data:
      title: Perturbation métro B
      message: "{{ state_attr(trigger.entity_id, 'titre') }}"
```

> Les identifiants d'entités ci-dessus sont des exemples : reprenez ceux de votre appareil (Paramètres → Appareils et services → TCL Lyon).

## Horaires théoriques (GTFS)

Quand le temps réel est vide (la nuit, ou service terminé), l'intégration complète avec les horaires théoriques du GTFS officiel TCL, téléchargé automatiquement chaque semaine avec vos identifiants (fichier `tcl_gtfs.zip` dans votre dossier de config, ~50-100 Mo). L'index se construit en tâche de fond au premier démarrage : les départs théoriques peuvent mettre quelques minutes à apparaître la première fois. Sur la carte, un départ à plus d'une heure s'affiche « HH:MM » plutôt qu'en minutes.

## Sources de données

| Source | Contenu | Rôle |
|---|---|---|
| SIRI Lite `estimated-timetables` | toutes les courses suivies par le SAE : heure théorique + estimée, suppressions | temps réel étendu (retards, plus de 2 passages) — flux **irrégulier**, jamais bloquant |
| `tcl_sytral.tclpassagearret` | 2 prochains passages par ligne et par arrêt, type E (estimé) / T (théorique) | temps réel de base |
| `tcl_sytral.tclalertetrafic_2` | alertes trafic (titre, message, début/fin) | capteur « Perturbation », bandeau de la carte (rafraîchi toutes les 5 min) |
| GTFS TCL | horaires théoriques | complément la nuit / en fin de service |

Les passages des différentes sources sont fusionnés sans doublon (même course, ou même destination à ±90 s). Quand le flux SIRI ne répond pas, l'intégration continue avec `tclpassagearret` sans erreur ni avertissement répété.

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

1. Activez les logs debug et guettez notamment l'avertissement « Aucun passage ne correspond à la direction configurée » (direction obsolète → changez-la dans les **options** de l'entrée) :

```yaml
logger:
  logs:
    custom_components.tcl: debug
```

2. Lancez le script de diagnostic (Python 3.9+, aucune dépendance) qui vérifie chaque maillon — station, temps réel, filtre de direction, GTFS, flux SIRI et alertes trafic :

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
