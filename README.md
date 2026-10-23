# Beit haMillon · בית המילון

Eigenständiges Studienwörterbuch für Hebräisch und Aramäisch: Jastrow, Klein, BDB, eigene Wortbedeutungen und Quelltexte. Weboberfläche auf Deutsch, Englisch und Hebräisch.

## Webversion

Veröffentlichung über GitHub Pages: https://moriahise.github.io/Jastrow/

- Suche mit und ohne Niqqud sowie nach deutschen und englischen Bedeutungen.
- Alle **32.512 Datensätze** des übernommenen Jastrow-Datenstands, zusätzlich die bisherigen Fassungen aus ZIP und Repository.
- Klein: vorhandene Definitionen plus Verzeichnis von **26.922 Stichwörtern**; fehlende Definitionen sind gekennzeichnet. Ein fortsetzbarer Sammler übernimmt sie einmalig von Sefaria und speichert sie im Browser.
- 115 Quelltexte mit vollständigem Wortstellenindex, Textleser und Nachschlagen per Wortklick.
- DE/EN/HE-Ergänzungen, Notizen, Merkliste, Suchverlauf und Export/Import ohne Überschreiben abweichender Fassungen.
- Offline-Speicherung der Wörterbücher oder des gesamten Bestands.
- Alle 142 Originaldateien des hochgeladenen ZIP bleiben byteidentisch rekonstruierbar und einzeln herunterladbar. Bestehende Repository-Dateien bleiben erhalten.

**Sprachabdeckung:** Hebräische Stichwörter und englische Wörterbuchoriginale sind vorhanden. Deutsche Wortbedeutungen aus dem Altbestand wurden übernommen. Vollständige deutsche und hebräische Übersetzungen aller Jastrow-/Klein-Artikel liegen noch nicht vor. Fehlende Übersetzungen sind ausdrücklich markiert; eigene Ergänzungen stehen neben dem Original.

**Persönliche Ergänzungen** werden in IndexedDB dieses Browsers gespeichert, nicht automatisch in GitHub oder zwischen Geräten synchronisiert. Regelmäßig unter „Bestand & Sicherung“ exportieren. Import auf einem anderen Gerät ist möglich. Der vollständige Klein-Abruf braucht eine geöffnete Seite und kann viele Stunden dauern. Einträge laufen nicht nach sieben Tagen ab.

## Lokal starten / prüfen

Python 3.10+ und Node.js 20+ genügen; keine Python-/npm-Pakete erforderlich.

```bash
python scripts/web/prepare_inputs.py
python scripts/web/build_data.py
python scripts/web/verify_data.py
node --test tests/search.test.mjs
python -m http.server 8080 --directory web
```

Dann http://localhost:8080 öffnen. `index.html` per Doppelklick ist wegen Browser-Sicherheitsregeln für Worker und lokale Datendateien nicht ausreichend. Die vorhandene PC-Anwendung (`start_manual.bat`) bleibt weiter nutzbar.

## Datenerhaltung und Veröffentlichung

`snapshots/upload-2026-10-23/manifest.json` hält jeden Originalpfad mit Größe und SHA-256 fest. Eine datensparsame Rekonstruktionsdatei erhält die Abweichungen gegenüber dem bestehenden Git-Commit, einschließlich ursprünglicher Zeilenenden. Der Build überprüft alle 142 Dateien vor der Veröffentlichung. Zusätzlich werden abweichende Wörterbuch- und Übersetzungsdatensätze des aktuellen Repository-Bestands übernommen. `web/data/verification.json` enthält den Prüfbericht.

Der GitHub-Actions-Workflow prüft den Datenbestand und die Suche und veröffentlicht ausschließlich `web/`. PC-Konfiguration und Build-Werkzeuge gelangen nicht in das Pages-Artefakt. Die Originale im öffentlichen Repository sind weiterhin über GitHub zugänglich.

Jastrow-Datenstand: Marcus Jastrow (1903), Public Domain; Digitalisierung von Sefaria, Datenübernahme über https://jastrow.us/data/. Klein: Ernest Klein, Carta (1987), Sefaria nennt CC-BY-NC. Herkunft und Originaldaten werden am Eintrag angezeigt. Für die übrigen übernommenen Quellen gelten deren jeweilige Rechte. Upstream-Dateien werden mit SHA-256 geprüft; geänderte Datenstände benötigen eine bewusste Aktualisierung der Prüfsummen in `scripts/web/upstream-pins.json`.
