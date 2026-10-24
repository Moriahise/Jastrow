# Beit haMillon · בית המילון

Öffentliches Studienwörterbuch: **Jastrow, Klein, BDB und Strong’s**.

Online: https://moriahise.github.io/Jastrow/

## Öffentlicher Bestand

- Jastrow: alle 32.512 Datensätze des geprüften Spiegelbestands, zusätzlich erhaltene offizielle Wörterbuchfassungen.
- Klein: zentral gesammelte Definitionen und nachvollziehbar markierte fehlende Stichwörter. Der Status in `data/klein-collection-status.json` ist maßgeblich; fehlende Definitionen werden nicht erfunden.
- BDB: der vorhandene Teilbestand einschließlich BDB Aramaic und BDB Augmented Strong.
- Strong’s: alle 8.674 hebräischen und aramäischen Einträge (H1–H8674), einschließlich Quellen- und Urheberangaben. Original: `openscriptures/strongs`, Commit `0acd2f251c2d35ff8db2dece4e0593979d3ac223`, `hebrew/StrongHebrewG.xml` (Public Domain laut XML-Werkmetadaten).

Die Oberfläche ist auf Deutsch, Englisch und Hebräisch verfügbar. Wörterbuchartikel stehen im englischen Original; vollständige DE-/HE-Artikelübersetzungen sind nicht enthalten.

## Quellenbibliothek

114 öffentliche Talmud-Quelltexte werden direkt mit der Website ausgeliefert. Auswahl nach Werk, Ausgabe und Daf; die Formatierung bleibt erhalten. Ein Mausklick oder Enter auf einem hebräischen Wort öffnet sofort das Wörterbuch, setzt die Suche auf alle vier Wörterbücher und berücksichtigt mögliche Vorsilben. „Zurück zur Lesestelle“ erhält Werk und Abschnitt.

Der Katalog enthält außerdem die 6.464 Werke der Shiurim-Quellenbibliothek (pinnierter Datenstand). Zusätzliche Texte werden erst beim Öffnen über die öffentliche Sefaria-Text-API geladen und als **online** gekennzeichnet. Für die direkt gespeicherten Texte und Wörterbücher ist keine Sefaria-Verbindung erforderlich. Eingefügte Studientexte bleiben im Arbeitsspeicher des Browsers und werden nicht veröffentlicht.

## Öffentlicher Lernraum

Für alle Besucher stehen Themenwortschatz, Wort des Tages, Alphabetnavigation und ein Wörterbuchvergleich zur Verfügung. Es gibt keine persönlichen Sammlungen, Notizdatenbanken oder übernommenen Suchverläufe.

## Bereinigung

Die persönlichen Suchverläufe, lokalen Wortbedeutungen, Übersetzungsarchive, Audiodateien, PC-Konfigurationen und Desktop-Programme wurden aus dem aktuellen Repository- und Website-Bestand entfernt. Die frühere ZIP-Rekonstruktion wird nicht mehr verwendet. Der separate Wörterbuch-Zusatzbestand enthält ausschließlich originale Jastrow-, Klein- und BDB-Datensätze ohne frühere Suchanfragen/Aliase. Alte Website-Caches werden bei der Aktivierung dieser öffentlichen Version entfernt. Die Git-Versionsgeschichte bleibt unverändert.

## Build und Prüfung

Python 3.10+ und Node.js 20+, keine zusätzlichen Pakete:

```bash
python scripts/web/prepare_inputs.py
python scripts/web/build_data.py
python scripts/web/verify_data.py
node --test tests/search.test.mjs
```

Der Build startet mit einem leeren Daten-Ausgabeverzeichnis und erlaubt ausschließlich die vier Wörterbuchfamilien. Er prüft Jastrow-RIDs, sämtliche Strong’s-Datensätze, die unveränderte Strong’s-XML und alle 114 Quelltexte. `web/data/verification.json` dokumentiert den veröffentlichten Stand. Modul-, CSS- und Datenversionen verhindern, dass alte persönliche Inhalte aus früheren Caches erneut eingebunden werden.

GitHub Actions veröffentlicht ausschließlich `web/`. Wörterbücher und gespeicherte Quelltexte lassen sich über „Bestand & Quellen“ offline auf dem jeweiligen Gerät speichern. Die einzige Browser-Präferenz ist die ausgewählte Oberflächensprache.

## Herkunft

Jastrow: Marcus Jastrow (1903), Public Domain; Digitalisierung Sefaria, Datenstand über jastrow.us. Klein: Ernest Klein, Carta (1987), Sefaria CC-BY-NC. BDB: Brown, Driver & Briggs, Herkunft je Datensatz. Strong’s: Open Scriptures on GitHub; ergänzende Urheberangabe „Based on the work of Larry Pierce at the Online Bible“; James Strong und XML-Herausgeber David Troidl / David Instone-Brewer. Rechte und Fassungen der Online-Texte werden beim Lesen angezeigt.
