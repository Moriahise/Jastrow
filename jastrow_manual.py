#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jastrow Dictionary - Vollständige Sefaria-Style Version
Mit Sefaria API, OpenAI Übersetzung, eigenem Wörterbuch und dauerhafter Speicherung

Features:
- Sefaria-Style Ausgabe (wie Original)
- Sefaria API Integration mit Cache
- OpenAI API Übersetzung (DE/EN)
- Eigenes Wörterbuch erstellen
- Dauerhafte Abfrage-Speicherung (query_history.json)
- Strg+C Clipboard-Monitoring (hardcodiert)
- 16 Gematria-Methoden
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tkinter as tk
from tkinter import messagebox, font as tkfont, simpledialog, ttk, filedialog
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
    import pyperclip
except ImportError as e:
    print("=" * 50)
    print("FEHLER: Benoetigte Pakete fehlen!")
    print("=" * 50)
    print(f"\nFehlend: {e}")
    print("\nBitte installiere mit: pip install pystray pillow pyperclip")
    exit(1)


# =============================================================================
# SEFARIA API
# =============================================================================

class SefariaAPI:
    """
    Sefaria API Client für Lexikon‑Abfragen.

    Neben dem eigentlichen HTTP‑Aufruf verwaltet dieser Client einen
    persistenten Cache. Die Gültigkeit des Caches (in Tagen) kann über
    ``cache_days`` gesteuert werden. Standardmäßig beträgt die Dauer
    sieben Tage, kann aber durch einen Eintrag ``sefaria_cache_days``
    in der Konfigurationsdatei angepasst werden.
    """

    BASE_URL = "https://www.sefaria.org/api"

    def __init__(self, cache_dir: Path, cache_days: int = 7):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = cache_dir / 'sefaria_lexicon_cache.json'
        self.cache = self._load_cache()
        self.enabled = True
        # Dauer in Tagen, wie lange Cache‑Einträge gültig sind
        try:
            self.cache_days = int(cache_days)
        except Exception:
            self.cache_days = 7
    
    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARNUNG] Sefaria-Cache speichern: {e}")
    
    def lookup_word(self, word: str) -> Optional[List[dict]]:
        """Sucht ein Wort in der Sefaria Lexikon‑API unter Berücksichtigung des Caches."""
        if not self.enabled:
            return self.cache.get(word, {}).get('data')

        # Cache prüfen (Gültigkeit in self.cache_days)
        if word in self.cache:
            cache_entry = self.cache[word]
            ts = cache_entry.get('timestamp')
            if ts:
                try:
                    cached_time = datetime.fromisoformat(ts)
                    # Wenn innerhalb der erlaubten Anzahl von Tagen, direkt aus Cache liefern
                    if (datetime.now() - cached_time).days < self.cache_days:
                        return cache_entry.get('data')
                except Exception:
                    # Bei fehlerhaften Zeitstempeln den Eintrag ignorieren
                    pass
        
        # API-Abfrage
        try:
            encoded_word = urllib.parse.quote(word)
            url = f"{self.BASE_URL}/words/{encoded_word}"
            
            req = urllib.request.Request(url, headers={
                'User-Agent': 'JastrowDictionary/2.0',
                'Accept': 'application/json'
            })
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                self.cache[word] = {
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }
                self._save_cache()
                return data
                
        except urllib.error.HTTPError as e:
            print(f"[SEFARIA] HTTP-Fehler {e.code}")
        except urllib.error.URLError as e:
            print(f"[SEFARIA] Verbindungsfehler")
        except Exception as e:
            print(f"[SEFARIA] Fehler: {e}")
        
        # Bei Fehler: Cache versuchen
        if word in self.cache:
            return self.cache[word].get('data')
        return None


class SefariaEntryFormatter:
    """Formatiert Sefaria Lexikon-Einträge"""
    
    @staticmethod
    def format_entry(entry: dict) -> dict:
        result = {
            'headword': entry.get('headword', ''),
            'headword_voweled': entry.get('headword', ''),
            'lexicon': entry.get('parent_lexicon', 'Unknown'),
            'rid': entry.get('rid', ''),
            'language': entry.get('language_code', ''),
            'pos': '',
            'definitions': [],
            'refs': entry.get('refs', []),
            'etymology': '',
            'derivatives': [],
            'notes': ''
        }
        
        content = entry.get('content', {})
        if isinstance(content, dict):
            senses = content.get('senses', [])
            result['definitions'] = SefariaEntryFormatter._parse_senses(senses)
            
            if 'morphology' in content:
                result['pos'] = content['morphology']
            if 'etymology' in content:
                result['etymology'] = content['etymology']
            if 'derivatives' in content:
                result['derivatives'] = content['derivatives']
        
        lang_code = entry.get('language_code', '')
        if 'm.' in lang_code or 'n.' in lang_code:
            result['pos'] = lang_code.strip()
        
        return result
    
    @staticmethod
    def _parse_senses(senses: list, depth: int = 0) -> list:
        definitions = []
        for sense in senses:
            if isinstance(sense, dict):
                if 'definition' in sense:
                    def_text = sense['definition']
                    def_text = re.sub(r'<[^>]+>', '', def_text)
                    definitions.append({
                        'text': def_text,
                        'depth': depth,
                        'grammar': sense.get('grammar', {}),
                        'notes': sense.get('notes', '')
                    })
                if 'senses' in sense:
                    definitions.extend(
                        SefariaEntryFormatter._parse_senses(sense['senses'], depth + 1)
                    )
        return definitions


# =============================================================================
# USER DICTIONARY
# =============================================================================

class SefariaTranslationDictionary:
    """
    Neues Wörterbuch für Sefaria-Übersetzungen.
    Dieses Wörterbuch speichert für jedes Wort eine Liste von Übersetzungen
    zusammen mit dem originalen Jastrow-Eintragstext. Damit können
    zukünftige Abfragen auf diese Übersetzungen zugreifen und sie als
    eigenes Wörterbuch nutzen. Das Format ist ähnlich wie beim
    Benutzerwörterbuch, enthält aber explizit den Originaltext und die
    API‑Übersetzung.
    """

    def __init__(self, dict_file: Path):
        self.dict_file = dict_file
        self.entries = self._load()

    def _load(self) -> dict:
        if self.dict_file.exists():
            try:
                with open(self.dict_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.dict_file, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FEHLER] Sefaria-Übersetzungswörterbuch speichern: {e}")

    def add_entry(self, word: str, original: str, translation: str):
        """
        Fügt einen übersetzten Eintrag hinzu. Mehrere Übersetzungen pro Wort
        werden als Liste gespeichert.
        """
        # Entferne Niqqud zur Normalisierung
        word_clean = ''.join(c for c in word if not ('\u0591' <= c <= '\u05C7')).strip()
        timestamp = datetime.now().isoformat()

        if not original and not translation:
            return
        if word_clean not in self.entries:
            self.entries[word_clean] = []
        # Verhindere Duplikate: gleiche Originale und Übersetzungen
        for entry in self.entries[word_clean]:
            if entry.get('original') == original and entry.get('translation') == translation:
                return
        self.entries[word_clean].append({
            'word_original': word,
            'original': original,
            'translation': translation,
            'added': timestamp
        })
        self._save()

    def get_entries(self, word: str) -> List[dict]:
        """Gibt alle gespeicherten Übersetzungen für ein Wort zurück."""
        word_clean = ''.join(c for c in word if not ('\u0591' <= c <= '\u05C7')).strip()
        return self.entries.get(word_clean, [])


class JastrowWordsDictionary:
    """
    Verwaltet eine Sammlung von Jastrow-Einträgen in JSON-Dateien.
    Jeder einzelne Wörterbucheintrag (Hebräisches Wort) wird alphabetisch
    sortiert gespeichert. Wenn eine Datei größer als `max_size` ist, wird
    automatisch eine neue Datei angelegt und ein Index aktualisiert.
    """

    def __init__(self, dir_path: Path, max_file_size_mb: int = 20):
        self.dir_path = dir_path
        self.dir_path.mkdir(exist_ok=True)
        self.max_size = max_file_size_mb * 1024 * 1024
        self.index_file = self.dir_path / 'index.json'
        self.files = []  # Liste der Wörterbuchdateien
        self._load_index()

    def _load_index(self):
        """
        Lade die Liste der Wörterbuchdateien.  Falls ein Index vorhanden ist,
        werden dessen Einträge gelesen. Zusätzlich werden alle vorhandenen
        ``jastrow_words_*.json`` Dateien im Verzeichnis berücksichtigt, um
        sicherzustellen, dass bereits existierende Wörterbuchdateien nicht
        verloren gehen, falls der Index beschädigt oder unvollständig ist.
        Sollte noch keine Datei existieren, wird eine neue leere Datei
        angelegt.
        """
        files_from_index: List[str] = []
        # Lade vorhandene Einträge aus dem Index (falls vorhanden)
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        files_from_index = [str(item) for item in data]
            except Exception:
                # Ignoriere Fehler – wir werden die Dateien aus dem Dateisystem lesen
                pass
        # Sammle alle Wörterbuchdateien im Verzeichnis
        discovered_files: List[str] = []
        try:
            for f in sorted(self.dir_path.glob('jastrow_words_*.json')):
                discovered_files.append(f.name)
        except Exception:
            pass
        # Kombiniere Index und entdeckte Dateien, ohne Duplikate
        combined: List[str] = []
        for fname in files_from_index + discovered_files:
            if fname not in combined:
                combined.append(fname)
        # Wenn noch keine Dateien vorhanden sind, erzeuge eine neue leere Datei
        if not combined:
            initial = 'jastrow_words_1.json'
            combined = [initial]
            path = self.dir_path / initial
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        # Aktualisiere die interne Liste und speichere den Index
        self.files = combined
        # Speichere den Index, um fehlende Dateien zu integrieren
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.files, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_index(self):
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.files, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _remove_niqqud(text: str) -> str:
        return ''.join(c for c in text if not ('\u0591' <= c <= '\u05C7'))

    def _get_current_file_path(self) -> Path:
        if not self.files:
            self._load_index()
        return self.dir_path / self.files[-1]

    def _create_new_file(self):
        # Erzeuge neuen Dateinamen basierend auf Anzahl der Dateien
        new_name = f"jastrow_words_{len(self.files) + 1}.json"
        self.files.append(new_name)
        self._save_index()
        # Schreibe leeres Wörterbuch in neue Datei
        try:
            with open(self.dir_path / new_name, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_entry(self, word: str, entry: dict):
        """Fügt einen Eintrag hinzu. Sortiert alphabetisch und prüft Datei-Größe."""
        if not word:
            return
        # Benutze bereinigtes Wort als Schlüssel
        clean_word = self._remove_niqqud(word).strip()
        # Lehne leere Schlüssel ab; Leerzeichen im Wort werden erlaubt, damit
        # zusammengesetzte Kopfwörter (z. B. Begriffe mit mehreren Wörtern) ebenfalls
        # im Wörterbuch gespeichert werden. Dadurch gehen solche Abfragen nicht
        # verloren.
        if not clean_word:
            return
        # Lade aktuelle Datei
        path = self._get_current_file_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        # Fügt den Eintrag hinzu
        if clean_word not in data:
            data[clean_word] = []
        # Verhindere doppelte Einträge anhand rid oder Definitionen
        def unique_check(new_entry, existing_entries):
            try:
                rid_new = new_entry.get('rid', '')
                defs_new = [d.get('text', '') for d in new_entry.get('definitions', [])]
                for old in existing_entries:
                    rid_old = old.get('rid', '')
                    defs_old = [d.get('text', '') for d in old.get('definitions', [])]
                    if rid_new and rid_new == rid_old:
                        return False
                    if defs_new and defs_new == defs_old:
                        return False
            except Exception:
                pass
            return True
        if unique_check(entry, data[clean_word]):
            data[clean_word].append(entry)
        # Sortiere Daten nach alphabetischer Reihenfolge der Schlüssel
        sorted_keys = sorted(data.keys(), key=lambda k: self._remove_niqqud(k))
        sorted_data = {k: data[k] for k in sorted_keys}
        # Speichere zurück
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        # Prüfe Größe und erstelle ggf. neue Datei
        try:
            if path.stat().st_size > self.max_size:
                # Neue Datei wird angelegt; nächste Einträge gehen dorthin
                self._create_new_file()
        except Exception:
            pass

    def get_all_entries(self) -> List[tuple]:
        """Gibt alle Wörter (Schlüssel) zurück, zusammen mit Dateinamen."""
        entries = []
        for fname in self.files:
            path = self.dir_path / fname
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for word in data.keys():
                        entries.append((word, fname))
            except Exception:
                pass
        # Sortiere global
        entries.sort(key=lambda x: self._remove_niqqud(x[0]))
        return entries

    def get_entry(self, word: str) -> Optional[List[dict]]:
        """Holt die gespeicherten Einträge für ein Wort aus den Dateien"""
        clean_word = self._remove_niqqud(word).strip()
        for fname in self.files:
            path = self.dir_path / fname
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if clean_word in data:
                        return data[clean_word]
            except Exception:
                pass
        return None


class UserDictionary:
    """Eigenes Wörterbuch für benutzerdefinierte Einträge"""
    
    def __init__(self, dict_file: Path):
        self.dict_file = dict_file
        self.entries = self._load()
    
    def _load(self) -> dict:
        if self.dict_file.exists():
            try:
                with open(self.dict_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save(self):
        try:
            with open(self.dict_file, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FEHLER] Wörterbuch speichern: {e}")
    
    def add_entry(self, word: str, de: str, en: str, notes: str = ""):
        word_clean = self._clean(word)
        timestamp = datetime.now().isoformat()
        
        if word_clean not in self.entries:
            self.entries[word_clean] = []
        
        self.entries[word_clean].append({
            'word_original': word,
            'de': de,
            'en': en,
            'notes': notes,
            'added': timestamp,
            'source': 'user'
        })
        self._save()
    
    def get_entries(self, word: str) -> List[dict]:
        return self.entries.get(self._clean(word), [])
    
    @staticmethod
    def _clean(text: str) -> str:
        text = ''.join(c for c in text if not ('\u0591' <= c <= '\u05C7'))
        return text.strip()


class ApiTranslationStore:
    """
    Speichert jede mittels API erstellte Übersetzung. Die Einträge werden
    in mehreren JSON‑Dateien verwaltet, die automatisch rotiert werden,
    wenn sie eine bestimmte Größe überschreiten. Ein Indexfile behält
    den Überblick über alle Teildateien.

    Jeder Eintrag enthält:
    - original: der übersetzte Text (Hebräisch/Aramäisch)
    - translation: die erzeugte Übersetzung
    - word: das ursprüngliche Suchwort, zu dem die Übersetzung gehörte
    - timestamp: Zeitpunkt der Erstellung
    """

    def __init__(self, dir_path: Path, max_file_size_mb: int = 20):
        self.dir_path = dir_path
        self.dir_path.mkdir(exist_ok=True)
        self.max_size = max_file_size_mb * 1024 * 1024
        self.index_file = self.dir_path / 'index.json'
        self.files = []
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.files = data
            except Exception:
                pass
        if not self.files:
            initial = 'translations_1.json'
            self.files = [initial]
            path = self.dir_path / initial
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                self._save_index()
            except Exception:
                pass

    def _save_index(self):
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.files, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_current_file_path(self) -> Path:
        if not self.files:
            self._load_index()
        return self.dir_path / self.files[-1]

    def _create_new_file(self):
        new_name = f"translations_{len(self.files) + 1}.json"
        self.files.append(new_name)
        self._save_index()
        try:
            with open(self.dir_path / new_name, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _remove_niqqud(text: str) -> str:
        return ''.join(c for c in text if not ('\u0591' <= c <= '\u05C7'))

    def add_translation(self, original: str, translation: str, word: str):
        if not original or not translation:
            return
        clean_key = self._remove_niqqud(original).strip()
        if not clean_key:
            return
        path = self._get_current_file_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        if clean_key not in data:
            data[clean_key] = []
        # Prüfe auf Duplikate: gleiche Übersetzung und Wort
        for entry in data[clean_key]:
            if entry.get('translation') == translation and entry.get('word') == word:
                break
        else:
            data[clean_key].append({
                'original': original,
                'translation': translation,
                'word': word,
                'timestamp': datetime.now().isoformat()
            })
        # Sortiere Schlüssel global
        sorted_keys = sorted(data.keys(), key=lambda k: self._remove_niqqud(k))
        sorted_data = {k: data[k] for k in sorted_keys}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        # Prüfe Größe der Datei
        try:
            if path.stat().st_size > self.max_size:
                self._create_new_file()
        except Exception:
            pass

    def get_translations(self, original: str, max_age_days: int = 0) -> List[dict]:
        """
        Liefert alle Übersetzungen zu einem Originaltext. Optional kann
        mittels ``max_age_days`` die maximale Gültigkeit der Einträge
        gesteuert werden. Wenn ``max_age_days`` > 0 angegeben ist, werden
        nur Übersetzungen berücksichtigt, deren Zeitstempel nicht älter
        als diese Anzahl von Tagen ist. Andernfalls werden alle
        gespeicherten Übersetzungen zurückgegeben.
        """
        clean_key = self._remove_niqqud(original).strip()
        results = []
        for fname in self.files:
            path = self.dir_path / fname
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if clean_key in data:
                        entries = data[clean_key]
                        if max_age_days and max_age_days > 0:
                            for entry in entries:
                                try:
                                    ts = entry.get('timestamp')
                                    if ts:
                                        t = datetime.fromisoformat(ts)
                                        if (datetime.now() - t).days <= max_age_days:
                                            results.append(entry)
                                except Exception:
                                    # Bei fehlerhaften Zeitstempeln als ungültig behandeln
                                    pass
                        else:
                            results.extend(entries)
            except Exception:
                pass
        return results

    def get_all_entries(self) -> List[Tuple[str, str]]:
        """Gibt alle Original‑Texte (Schlüssel) zurück, zusammen mit Dateinamen."""
        entries = []
        for fname in self.files:
            path = self.dir_path / fname
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key in data.keys():
                        entries.append((key, fname))
            except Exception:
                pass
        entries.sort(key=lambda x: self._remove_niqqud(x[0]))
        return entries


# =============================================================================
# QUERY HISTORY
# =============================================================================

class QueryHistory:
    """Dauerhafte Abfrage-Historie mit API-Übersetzungen"""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        # Anzahl der zu speichernden Einträge begrenzen?  Standardmässig unbegrenzt.
        # Das Wörterbuch soll alle Abfragen dauerhaft behalten, daher setzen wir
        # die Begrenzung auf None. Wird in ``add_query`` berücksichtigt.
        self.max_entries: Optional[int] = None
        self.history = self._load()
    
    def _load(self) -> dict:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {'queries': data, 'stats': {'total_queries': len(data)}}
                    return data
            except:
                pass
        return {'queries': [], 'stats': {'total_queries': 0}}
    
    def _save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FEHLER] Historie speichern: {e}")
    
    def add_query(self, word: str, translations: List[Tuple], sources: List[dict], 
                  gematria: int, sefaria_count: int = 0, api_translation: str = None, api_lang: str = None):
        """Speichert JEDE Abfrage"""
        word_clean = ''.join(c for c in word if not ('\u0591' <= c <= '\u05C7')).strip()
        timestamp = datetime.now().isoformat()
        
        # Formatiere
        trans_formatted = []
        for item in translations[:10]:
            if isinstance(item, tuple) and len(item) >= 3:
                de, en, tract = item
                trans_formatted.append({
                    'de': str(de)[:300] if de else '',
                    'en': str(en)[:300] if en else '',
                    'tractate': str(tract)[:100] if tract else ''
                })
        
        sources_formatted = []
        for src in sources[:5]:
            sources_formatted.append({
                'path': str(src.get('path_str', ''))[:150],
                'line': src.get('line', 0),
                'context': str(src.get('context', ''))[:300]
            })
        
        # Existierenden Eintrag suchen
        existing_idx = None
        for i, entry in enumerate(self.history['queries']):
            if entry.get('word_clean') == word_clean:
                existing_idx = i
                break
        
        if existing_idx is not None:
            entry = self.history['queries'][existing_idx]
            entry['query_count'] = entry.get('query_count', 1) + 1
            entry['last_query'] = timestamp
            entry['sefaria_count'] = sefaria_count
            
            if api_translation:
                if 'api_translations' not in entry:
                    entry['api_translations'] = {}
                entry['api_translations'][api_lang or 'de'] = {
                    'text': api_translation,
                    'timestamp': timestamp
                }
            
            self.history['queries'].pop(existing_idx)
            self.history['queries'].insert(0, entry)
        else:
            new_entry = {
                'word': word,
                'word_clean': word_clean,
                'gematria': gematria,
                'translations': trans_formatted,
                'sources': sources_formatted,
                'sefaria_count': sefaria_count,
                'first_query': timestamp,
                'last_query': timestamp,
                'query_count': 1
            }
            if api_translation:
                new_entry['api_translations'] = {
                    api_lang or 'de': {'text': api_translation, 'timestamp': timestamp}
                }
            self.history['queries'].insert(0, new_entry)
        
        # Wenn eine maximale Anzahl von Einträgen definiert ist und diese überschritten
        # wird, beschneiden wir die Liste. Standardmässig ist ``max_entries`` None,
        # sodass keine Beschneidung stattfindet und alle Abfragen erhalten bleiben.
        if self.max_entries is not None and self.max_entries > 0 and len(self.history['queries']) > self.max_entries:
            self.history['queries'] = self.history['queries'][:self.max_entries]
        
        self.history['stats']['total_queries'] = self.history['stats'].get('total_queries', 0) + 1
        self.history['stats']['last_query'] = timestamp
        
        self._save()
    
    def update_api_translation(self, word: str, translation: str, lang: str):
        word_clean = ''.join(c for c in word if not ('\u0591' <= c <= '\u05C7')).strip()
        timestamp = datetime.now().isoformat()
        
        for entry in self.history['queries']:
            if entry.get('word_clean') == word_clean:
                if 'api_translations' not in entry:
                    entry['api_translations'] = {}
                entry['api_translations'][lang] = {'text': translation, 'timestamp': timestamp}
                self._save()
                return True
        return False
    
    def get_entry(self, word: str) -> Optional[dict]:
        word_clean = ''.join(c for c in word if not ('\u0591' <= c <= '\u05C7')).strip()
        for entry in self.history['queries']:
            if entry.get('word_clean') == word_clean:
                return entry
        return None
    
    def get_history(self, limit: int = 100) -> List[dict]:
        return self.history['queries'][:limit]
    
    def search_history(self, query: str) -> List[dict]:
        query_lower = query.lower()
        results = []
        for entry in self.history['queries']:
            if query_lower in entry.get('word', '').lower():
                results.append(entry)
                continue
            for trans in entry.get('translations', []):
                if query_lower in trans.get('de', '').lower() or query_lower in trans.get('en', '').lower():
                    results.append(entry)
                    break
        return results
    
    def get_stats(self) -> dict:
        stats = dict(self.history.get('stats', {}))
        stats['unique_words'] = len(self.history['queries'])
        if self.history['queries']:
            most = max(self.history['queries'], key=lambda x: x.get('query_count', 0))
            stats['most_queried'] = most.get('word', '')
            stats['most_queried_count'] = most.get('query_count', 0)
        return stats


# =============================================================================
# SOURCE INDEX
# =============================================================================

class SourceIndex:
    """Index für Quelltexte mit Cache"""
    
    def __init__(self, sources_path: Path):
        self.sources_path = sources_path
        self.cache_file = Path('.') / 'source_index.cache'
        self.file_index = {}
        self.file_count = 0
        self.line_count = 0
    
    def build_index(self):
        if not self.sources_path.exists():
            print(f"  [--] sources/ nicht gefunden")
            return
        
        current_stats = self._get_stats()
        if self._load_cache(current_stats):
            print(f"  [CACHE] {self.file_count} Dateien")
            return
        
        print("  Indexiere...")
        self.file_index = {}
        self.file_count = 0
        self.line_count = 0
        
        txt_files = list(self.sources_path.rglob("*.txt"))
        for i, f in enumerate(txt_files):
            try:
                self._index_file(f)
                self.file_count += 1
            except:
                pass
        
        self._save_cache(current_stats)
        print(f"  [OK] {self.file_count} Dateien, {self.line_count} Zeilen")
    
    def _get_stats(self) -> dict:
        stats = {'file_count': 0, 'total_size': 0, 'newest_mtime': 0}
        for f in self.sources_path.rglob("*.txt"):
            try:
                s = f.stat()
                stats['file_count'] += 1
                stats['total_size'] += s.st_size
                stats['newest_mtime'] = max(stats['newest_mtime'], s.st_mtime)
            except:
                pass
        return stats
    
    def _load_cache(self, current_stats: dict) -> bool:
        if not self.cache_file.exists():
            return False
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cached = data.get('stats', {})
            if cached.get('file_count') != current_stats['file_count'] or \
               cached.get('total_size') != current_stats['total_size']:
                return False
            
            self.file_index = {}
            for word, entries in data.get('index', {}).items():
                self.file_index[word] = [
                    {'file': Path(e['file']), 'line': e['line'], 'context': e['context']}
                    for e in entries
                ]
            self.file_count = cached['file_count']
            self.line_count = data.get('line_count', 0)
            return True
        except:
            return False
    
    def _save_cache(self, stats: dict):
        try:
            serializable = {}
            for word, entries in self.file_index.items():
                serializable[word] = [
                    {'file': str(e['file']), 'line': e['line'], 'context': e['context']}
                    for e in entries
                ]
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({'stats': stats, 'line_count': self.line_count, 'index': serializable}, f, ensure_ascii=False)
        except:
            pass
    
    def _index_file(self, file_path: Path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except:
            try:
                with open(file_path, 'r', encoding='cp1255') as f:
                    lines = f.readlines()
            except:
                return
        
        for i, line in enumerate(lines):
            self.line_count += 1
            for word in re.findall(r'[\u0590-\u05FF]+', line):
                word_clean = self._remove_niqqud(word)
                if len(word_clean) < 2:
                    continue
                if word_clean not in self.file_index:
                    self.file_index[word_clean] = []
                if len(self.file_index[word_clean]) < 15:
                    ctx_start = max(0, i - 1)
                    ctx_end = min(len(lines), i + 2)
                    context = ''.join(lines[ctx_start:ctx_end]).strip()
                    self.file_index[word_clean].append({
                        'file': file_path, 'line': i + 1, 'context': context[:400]
                    })
    
    @staticmethod
    def _remove_niqqud(text: str) -> str:
        return ''.join(c for c in text if not ('\u0591' <= c <= '\u05C7'))
    
    def get_source_path(self, file_path: Path) -> str:
        try:
            rel = file_path.relative_to(self.sources_path)
            parts = list(rel.parts[:-1])
            return " > ".join(parts) if parts else rel.stem
        except:
            return file_path.stem
    
    def find_sources(self, word: str) -> List[dict]:
        word_clean = self._remove_niqqud(word)
        word_clean = re.sub(r'[^\u0590-\u05FF]', '', word_clean)
        return self.file_index.get(word_clean, [])


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class JastrowDictionary:
    """Jastrow Dictionary - Hauptklasse mit Sefaria-Style Ausgabe"""
    
    def __init__(self):
        self.base_path = Path('.')
        self.dict_path = self.base_path / 'dictionaries'
        self.sources_path = self.base_path / 'sources'
        self.sefaria_cache_path = self.base_path / 'sefaria_cache'
        self.config_file = self.base_path / 'config.json'
        self.history_file = self.base_path / 'query_history.json'
        self.user_dict_file = self.base_path / 'user_dictionary.json'

        # Neues Wörterbuch für Sefaria‑Übersetzungen
        self.sefaria_translation_file = self.base_path / 'sefaria_translations.json'
        self.sefaria_translation_dict = SefariaTranslationDictionary(self.sefaria_translation_file)

        # Wörterbuch der einzelnen Jastrow‑Einträge (alphabetisch sortiert).
        # Dieses Wörterbuch speichert jeden gefundenen Sefaria‑Jastrow‑Eintrag
        # als eigenen Datensatz. Bei Überschreitung der max. Dateigröße wird
        # automatisch eine neue Datei angelegt und der Index aktualisiert.
        self.jastrow_dict = JastrowWordsDictionary(self.base_path / 'jastrow_words')

        # Speichert alle mittels API erstellten Übersetzungen (sowohl komplette
        # Sefaria‑Einträge als auch Auswahlen). Dateien werden automatisch
        # rotiert, wenn sie grösser als 20 MB werden.
        self.translation_store = ApiTranslationStore(self.base_path / 'api_translations')

        # Daten
        self.translations = {}
        self.word_to_ids = {}
        self.id_to_tractates = {}
        self.tractate_names = []
        self.sefaria_entries = {}

        # Config: Lädt Einstellungen (einschliesslich Cache‑Dauer) vor der
        # Instanzierung der API‑Komponente.
        self.config = self._load_config()

        # Komponenten
        # Übergebe die konfigurierbare Cache‑Dauer an den Sefaria‑Client.
        sefaria_days = self.config.get('sefaria_cache_days', 7)
        self.sefaria_api = SefariaAPI(self.sefaria_cache_path, cache_days=sefaria_days)
        self.source_index = SourceIndex(self.sources_path)
        self.query_history = QueryHistory(self.history_file)
        self.user_dictionary = UserDictionary(self.user_dict_file)

        # Clipboard
        self.check_interval = 250
        self.last_clipboard = ""
        self.monitoring = True  # HARDCODIERT
        self.icon = None
        self.clipboard_errors = 0

        # GUI
        self.root = tk.Tk()
        self.root.withdraw()
    
    def _load_config(self) -> dict:
        default = {
            'openai_api_key': '',
            'translation_language': 'de',
            'api_model': 'gpt-4o-mini',
            'sefaria_enabled': True,
            'auto_update_local': True,
            # Neue Konfigurationsparameter
            # Anzahl Tage, die Sefaria‑Cacheeinträge gültig bleiben sollen
            'sefaria_cache_days': 7,
            # Anzahl Tage, nach denen Übersetzungen erneut generiert werden sollen
            'translation_cache_days': 0
        }
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    default.update(json.load(f))
            except:
                pass
        return default
    
    def _save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    # ==================== OpenAI API ====================
    
    def _translate_with_openai(self, text: str, target_lang: str = None) -> Optional[str]:
        api_key = self.config.get('openai_api_key', '').strip()
        if not api_key:
            return None
        
        if target_lang is None:
            target_lang = self.config.get('translation_language', 'de')
        
        lang_name = 'German' if target_lang == 'de' else 'English'
        
        try:
            data = {
                'model': self.config.get('api_model', 'gpt-4o-mini'),
                'messages': [
                    {'role': 'system', 'content': f'Translate Hebrew/Aramaic religious texts to {lang_name}. Only translation, no notes.'},
                    {'role': 'user', 'content': f'Translate: {text}'}
                ],
                'max_tokens': 500,
                'temperature': 0.2
            }
            
            req = urllib.request.Request(
                'https://api.openai.com/v1/chat/completions',
                data=json.dumps(data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[API-FEHLER] {e}")
            return None
    
    # ==================== Laden ====================
    
    def load_files(self) -> bool:
        print()
        print("=" * 60)
        print("JASTROW DICTIONARY - Sefaria Style")
        print("=" * 60)
        print()
        
        print("[1/5] Lade Woerterbuecher...")
        dict_count = self._load_dictionaries()
        
        print()
        print("[2/5] Lade Wort-Mappings...")
        mapping_count = self._load_mappings()
        
        print()
        print("[3/5] Lade Sefaria-Cache...")
        self._load_sefaria_entries()
        
        print()
        print("[4/5] Indexiere Quelltexte...")
        self.source_index.build_index()
        
        print()
        print("[5/5] Lade Benutzer-Woerterbuch...")
        print(f"  [OK] {len(self.user_dictionary.entries)} Eintraege")
        
        stats = self.query_history.get_stats()
        
        print()
        print("=" * 60)
        print(f"  Woerterbuecher:       {dict_count}")
        print(f"  Wort-Mappings:        {mapping_count}")
        print(f"  Sefaria-Cache:        {len(self.sefaria_entries)}")
        print(f"  Quelldateien:         {self.source_index.file_count}")
        print(f"  Benutzer-Eintraege:   {len(self.user_dictionary.entries)}")
        print(f"  Gespeicherte Abfragen: {stats.get('unique_words', 0)}")
        print("=" * 60)
        print()
        
        return True
    
    def _load_dictionaries(self) -> int:
        count = 0
        for path in [self.dict_path, self.base_path]:
            if not path.exists():
                continue
            for dict_file in sorted(path.glob('merged_dict_*.json')):
                try:
                    name = dict_file.stem.replace('merged_dict_', '')
                    with open(dict_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for word_id in data.keys():
                        if word_id not in self.id_to_tractates:
                            self.id_to_tractates[word_id] = []
                        if name not in self.id_to_tractates[word_id]:
                            self.id_to_tractates[word_id].append(name)
                    
                    self.translations.update(data)
                    self.tractate_names.append(name)
                    print(f"  [OK] {name}: {len(data):,} Eintraege")
                    count += 1
                except Exception as e:
                    print(f"  [FEHLER] {dict_file.name}: {e}")
        return count
    
    def _load_mappings(self) -> int:
        count = 0
        skip = ['dict', 'history', 'config', 'cache', 'user_dictionary', 'sefaria']
        for path in [self.dict_path, self.base_path]:
            if not path.exists():
                continue
            for f in sorted(path.glob('*.json')):
                if any(s in f.name.lower() for s in skip):
                    continue
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        self._extract_words(json.load(file))
                    print(f"  [OK] {f.stem}")
                    count += 1
                except:
                    pass
        return count
    
    def _extract_words(self, data):
        if isinstance(data, list):
            for item in data:
                self._extract_words(item)
        elif isinstance(data, dict):
            for word, ids in data.items():
                if word and word.strip():
                    clean = self._remove_niqqud(word)
                    if clean not in self.word_to_ids:
                        self.word_to_ids[clean] = []
                    if isinstance(ids, list):
                        self.word_to_ids[clean].extend(ids)
                    elif isinstance(ids, str):
                        self.word_to_ids[clean].append(ids)
    
    def _load_sefaria_entries(self):
        """Laedt Sefaria-Cache"""
        cache = self.sefaria_api.cache
        for word, data in cache.items():
            if data.get('data'):
                word_clean = self._remove_niqqud(word)
                self.sefaria_entries[word_clean] = {
                    'entries': [SefariaEntryFormatter.format_entry(e) for e in data['data']]
                }
        print(f"  [OK] {len(self.sefaria_entries)} gecachte Eintraege")
    
    @staticmethod
    def _remove_niqqud(text: str) -> str:
        return ''.join(c for c in text if not ('\u0591' <= c <= '\u05C7'))
    
    @staticmethod
    def _clean_word(text: str) -> str:
        return re.sub(r'[\s.,;!?:\-\u2014\u2013()\[\]{}\'\"]+', '', text)
    
    # ==================== Suche ====================
    
    def search_word(self, word: str) -> dict:
        word_clean = self._clean_word(word)
        word_no_niqqud = self._remove_niqqud(word_clean)
        
        result = {
            'word': word.strip(),
            'translations': [],
            'sources': [],
            'sefaria_entries': [],
            'user_entries': []
        }
        
        # 1. Lokales Woerterbuch
        if word_no_niqqud in self.word_to_ids:
            for word_id in self.word_to_ids[word_no_niqqud]:
                if word_id in self.translations:
                    entry = self.translations[word_id]
                    tractates = self.id_to_tractates.get(word_id, ["?"])
                    tractate_str = ", ".join(tractates)
                    
                    if isinstance(entry, dict) and 'de' in entry and 'en' in entry:
                        result['translations'].append((entry['de'], entry['en'], tractate_str))
                    elif isinstance(entry, list):
                        for item in entry:
                            if isinstance(item, dict) and 'de' in item and 'en' in item:
                                result['translations'].append((item['de'], item['en'], tractate_str))
        
        # Duplikate entfernen
        seen = set()
        unique = []
        for de, en, tractate in result['translations']:
            if (de, en) not in seen:
                seen.add((de, en))
                unique.append((de, en, tractate))
        result['translations'] = unique
        
        # 2. Sefaria
        if self.config.get('sefaria_enabled', True):
            if word_no_niqqud in self.sefaria_entries:
                result['sefaria_entries'] = self.sefaria_entries[word_no_niqqud].get('entries', [])
            
            if not result['sefaria_entries']:
                def fetch():
                    data = self.sefaria_api.lookup_word(word_clean)
                    if data:
                        formatted = []
                        for e in data:
                            formatted_entry = SefariaEntryFormatter.format_entry(e)
                            formatted.append(formatted_entry)
                            result['sefaria_entries'].append(formatted_entry)
                            # Füge diesen Eintrag in das Jastrow‑Wörterbuch ein, falls vorhanden.
                            # Es wird nur das Kopfwort (ohne Niqqud) verwendet, um alphabetisch
                            # zu sortieren. Der Eintrag selbst wird vollständig gespeichert.
                            try:
                                headword = formatted_entry.get('headword') or ''
                                self.jastrow_dict.add_entry(headword, formatted_entry)
                            except Exception:
                                pass
                        # Speichere formatierte Einträge in sefaria_entries für spätere Verwendung
                        try:
                            self.sefaria_entries[word_no_niqqud] = {'entries': formatted}
                        except Exception:
                            pass
                thread = threading.Thread(target=fetch, daemon=True)
                thread.start()
                thread.join(timeout=2)
        
        # 3. Benutzer-Woerterbuch
        result['user_entries'] = self.user_dictionary.get_entries(word)
        
        # 4. Quellen
        sources = self.source_index.find_sources(word)
        for src in sources[:10]:
            src['path_str'] = self.source_index.get_source_path(src['file'])
        result['sources'] = sources[:10]
        
        # 5. Uebersetzungen aus dem Sefaria-Übersetzungswörterbuch
        try:
            result['translated_entries'] = self.sefaria_translation_dict.get_entries(word)
        except Exception:
            result['translated_entries'] = []

        # Füge alle vorhandenen Sefaria‑Einträge in das Wörterbuch ein (falls noch nicht
        # vorhanden). Dadurch werden auch aus dem Cache geladene Einträge
        # persistiert. Fehler werden ignoriert, Duplikate intern abgefangen.
        for entry in result.get('sefaria_entries', []):
            try:
                self.jastrow_dict.add_entry(entry.get('headword', ''), entry)
            except Exception:
                pass

        return result
    
    # ==================== Gematria ====================
    
    def _calculate_gematria(self, word: str) -> int:
        values = {
            'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
            'י': 10, 'כ': 20, 'ך': 20, 'ל': 30, 'מ': 40, 'ם': 40, 'נ': 50, 'ן': 50,
            'ס': 60, 'ע': 70, 'פ': 80, 'ף': 80, 'צ': 90, 'ץ': 90, 'ק': 100,
            'ר': 200, 'ש': 300, 'ת': 400
        }
        return sum(values.get(c, 0) for c in word)
    
    # ==================== GUI - Sefaria Style ====================
    
    def show_tooltip(self, word: str, search_result: dict):
        """Zeigt Sefaria-Style Fenster"""
        word = word.strip()
        
        win = tk.Toplevel(self.root)
        win.title(f"Jastrow: {word}")
        # Größeres Fenster für bessere Lesbarkeit
        # Größeres, skalierbares Fenster
        win.geometry("1100x1000")
        win.configure(bg='#ffffff')  # Weisser Hintergrund wie Sefaria
        
        # Fonts (Sefaria-Style)
        font_hebrew_large = ('David', 24)
        font_hebrew = ('David', 14)
        font_hebrew_small = ('David', 11)
        font_title = ('Georgia', 12, 'bold')
        font_normal = ('Georgia', 11)
        font_small = ('Georgia', 9)
        font_italic = ('Georgia', 10, 'italic')

        # Zusätzliche Schriften für POS und Referenzen im Text-Widget
        font_pos_text = ('Georgia', 11, 'italic')
        font_ref_text = ('Georgia', 9, 'italic')
        
        translations = search_result['translations']
        sources = search_result['sources']
        sefaria_entries = search_result.get('sefaria_entries', [])
        user_entries = search_result.get('user_entries', [])
        translated_entries = search_result.get('translated_entries', [])
        
        gematria = self._calculate_gematria(word)
        
        # Zur Historie speichern
        self.query_history.add_query(word, translations, sources, gematria, len(sefaria_entries))
        
        # === HEADER (Sefaria-Style) ===
        header_frame = tk.Frame(win, bg='#f5f5f5', pady=15)
        header_frame.pack(fill='x')
        
        search_frame = tk.Frame(header_frame, bg='#f5f5f5')
        search_frame.pack(fill='x', padx=20)
        
        tk.Label(search_frame, text="🔍", font=('Arial', 14), bg='#f5f5f5', fg='#666').pack(side='left')
        tk.Label(search_frame, text=word, font=font_hebrew_large, bg='#f5f5f5', fg='#000').pack(side='left', padx=10)
        tk.Label(search_frame, text=f"= {gematria}", font=font_small, bg='#f5f5f5', fg='#666').pack(side='left', padx=5)
        
        # Query-Count
        hist_entry = self.query_history.get_entry(word)
        if hist_entry and hist_entry.get('query_count', 0) > 1:
            tk.Label(search_frame, text=f"({hist_entry['query_count']}x)", 
                    font=font_small, bg='#f5f5f5', fg='#999').pack(side='left')
        
        tk.Button(search_frame, text="X", command=win.destroy, bg='#f5f5f5', fg='#666',
                 font=('Arial', 14), relief='flat', cursor='hand2', bd=0).pack(side='right', padx=10)
        
        # === TOOLBAR ===
        toolbar = tk.Frame(win, bg='#e8e8e8', pady=5)
        toolbar.pack(fill='x')
        
        btn_style = {'bg': '#ffffff', 'fg': '#333', 'font': font_small,
                    'relief': 'solid', 'bd': 1, 'padx': 8, 'pady': 3, 'cursor': 'hand2'}
        
        status_var = tk.StringVar()
        
        def copy_word():
            pyperclip.copy(word)
            status_var.set("Wort kopiert!")
            win.after(2000, lambda: status_var.set(""))
        
        def copy_all():
            text = self._format_full_entry(word, search_result)
            pyperclip.copy(text)
            status_var.set("Alles kopiert!")
            win.after(2000, lambda: status_var.set(""))
        
        def search_sefaria():
            import webbrowser
            webbrowser.open(f"https://www.sefaria.org/search?q={urllib.parse.quote(word)}")
        
        def refresh_sefaria():
            status_var.set("Aktualisiere...")
            def fetch():
                data = self.sefaria_api.lookup_word(word)
                if data:
                    status_var.set("Aktualisiert! Neu suchen.")
                else:
                    status_var.set("Keine Daten")
            threading.Thread(target=fetch, daemon=True).start()
        
        def api_translate():
            self._show_api_translation_dialog(word, win, status_var)
        
        def add_to_dict():
            self._show_add_to_dict_dialog(word, translations, win)

        # Zeigt den Volltext (Sefaria-Eintrag und Übersetzungen) in einem kopierbaren Textfeld
        def show_full_text():
            # Erzeuge den Volltext aus Sefaria-Einträgen und lokalen Übersetzungen
            text = self._format_full_entry(word, search_result)
            # Füge API-Übersetzungen aus der Historie hinzu
            hist_entry_local = self.query_history.get_entry(word)
            if hist_entry_local and hist_entry_local.get('api_translations'):
                for lang, trans in hist_entry_local['api_translations'].items():
                    lang_name = "Deutsch" if lang == 'de' else "English"
                    text += f"\n\n{lang_name} API-Übersetzung:\n{trans['text']}"
            # Füge gespeicherte Übersetzungen aus dem Sefaria-Wörterbuch hinzu
            translated = search_result.get('translated_entries', [])
            for t in translated:
                orig = t.get('original', '')
                trn = t.get('translation', '')
                if orig or trn:
                    text += "\n\n---\n"
                    if orig:
                        text += f"Original:\n{orig}\n"
                    if trn:
                        text += f"Übersetzung:\n{trn}\n"
            # Neues Fenster mit Textfeld
            full_win = tk.Toplevel(self.root)
            full_win.title(f"Volltext: {word}")
            full_win.geometry("800x600")
            full_win.configure(bg='#ffffff')
            text_widget = tk.Text(full_win, wrap='word', font=('Georgia', 11), bg='#fafafa')
            text_widget.pack(fill='both', expand=True)
            text_widget.insert('1.0', text)
            # Erlaube Benutzer, Text zu markieren und kopieren
            text_widget.configure(state='normal')
            # Füge Scrollbar hinzu
            scrollbar = tk.Scrollbar(full_win, command=text_widget.yview)
            scrollbar.pack(side='right', fill='y')
            text_widget['yscrollcommand'] = scrollbar.set
            # Schließen-Button
            tk.Button(full_win, text="Schliessen", command=full_win.destroy,
                     bg='#2196F3', fg='white', font=('Georgia', 10), relief='flat', padx=20).pack(pady=5)
        
        tk.Button(toolbar, text="Kopieren", command=copy_word, **btn_style).pack(side='left', padx=3)
        tk.Button(toolbar, text="Alles kopieren", command=copy_all, **btn_style).pack(side='left', padx=3)
        tk.Button(toolbar, text="Sefaria oeffnen", command=search_sefaria, **btn_style).pack(side='left', padx=3)
        tk.Button(toolbar, text="Aktualisieren", command=refresh_sefaria, **btn_style).pack(side='left', padx=3)
        
        tk.Frame(toolbar, width=2, bg='#ccc').pack(side='left', fill='y', padx=5, pady=2)
        
        tk.Button(toolbar, text="API Uebersetzen", command=api_translate,
                 bg='#FF9800', fg='white', font=font_small, relief='flat', 
                 padx=8, pady=3, cursor='hand2').pack(side='left', padx=3)
        tk.Button(toolbar, text="+ Woerterbuch", command=add_to_dict,
                 bg='#4CAF50', fg='white', font=font_small, relief='flat',
                 padx=8, pady=3, cursor='hand2').pack(side='left', padx=3)

        # Button zum Anzeigen des Volltexts mit Kopierfunktion
        tk.Button(toolbar, text="Volltext", command=show_full_text,
                 bg='#ffffff', fg='#333', font=font_small, relief='solid',
                 bd=1, padx=8, pady=3, cursor='hand2').pack(side='left', padx=3)
        
        tk.Button(toolbar, text="Einstellungen", command=self._show_api_settings, **btn_style).pack(side='right', padx=3)
        
        # === HAUPTBEREICH ===
        main_frame = tk.Frame(win, bg='#ffffff')
        main_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(main_frame, bg='#ffffff', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ffffff')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        
        content_frame = tk.Frame(scrollable_frame, bg='#ffffff', padx=25, pady=15)
        content_frame.pack(fill='both', expand=True)
        
        # === API-UEBERSETZUNG (wenn vorhanden) ===
        if hist_entry and hist_entry.get('api_translations'):
            api_frame = tk.Frame(content_frame, bg='#e3f2fd', pady=10, padx=15)
            api_frame.pack(fill='x', pady=(0, 15))
            
            tk.Label(api_frame, text="API-Uebersetzung", font=font_title, 
                    bg='#e3f2fd', fg='#1565C0').pack(anchor='w')
            
            for lang, trans in hist_entry['api_translations'].items():
                lang_name = "Deutsch" if lang == 'de' else "English"
                tk.Label(api_frame, text=f"{lang_name}: {trans['text']}", 
                        font=font_normal, bg='#e3f2fd', fg='#333',
                        wraplength=700, justify='left').pack(anchor='w', pady=2)
        
        # === BENUTZER-WOERTERBUCH ===
        if user_entries:
            user_frame = tk.Frame(content_frame, bg='#e8f5e9', pady=10, padx=15)
            user_frame.pack(fill='x', pady=(0, 15))
            
            tk.Label(user_frame, text="Eigenes Woerterbuch", font=font_title,
                    bg='#e8f5e9', fg='#2E7D32').pack(anchor='w')
            
            for entry in user_entries:
                tk.Label(user_frame, text=f"DE: {entry['de']}", font=font_normal,
                        bg='#e8f5e9', fg='#333').pack(anchor='w')
                tk.Label(user_frame, text=f"EN: {entry['en']}", font=font_italic,
                        bg='#e8f5e9', fg='#555').pack(anchor='w')
                if entry.get('notes'):
                    tk.Label(user_frame, text=f"Notiz: {entry['notes']}", font=font_small,
                            bg='#e8f5e9', fg='#666').pack(anchor='w')

        # === UEBERSETZTE SEFARIA-EINTRAEGE ===
        if translated_entries:
            trans_frame = tk.Frame(content_frame, bg='#fffde7', pady=10, padx=15)
            trans_frame.pack(fill='x', pady=(0, 15))
            tk.Label(trans_frame, text="Sefaria Übersetzungen", font=font_title,
                    bg='#fffde7', fg='#f57f17').pack(anchor='w')
            for entry in translated_entries:
                orig = entry.get('original', '')
                trans = entry.get('translation', '')
                # Original Text
                if orig:
                    tk.Label(trans_frame, text=f"Original: {orig}", font=font_normal,
                            bg='#fffde7', fg='#333', wraplength=700, justify='left').pack(anchor='w', pady=2)
                # Übersetzter Text
                if trans:
                    tk.Label(trans_frame, text=f"Übersetzung: {trans}", font=font_italic,
                            bg='#fffde7', fg='#555', wraplength=700, justify='left').pack(anchor='w', pady=(0,6))
        
        # === SEFARIA-EINTRAEGE ===
        # Anstelle von Labels wird ein Textfeld verwendet, das Markieren und Kopieren erlaubt
        if sefaria_entries:
            sef_frame = tk.Frame(content_frame, bg='#ffffff', pady=10, padx=15)
            sef_frame.pack(fill='x', pady=(0, 15))
            tk.Label(sef_frame, text="Sefaria Einträge", font=font_title,
                    bg='#ffffff', fg='#333').pack(anchor='w')
            # Textfeld für Sefaria‑Einträge mit eigener vertikaler Scrollbar. Durch die
            # Verwendung von fill='both' und expand=True ist das Widget responsiv.
            text_widget = tk.Text(sef_frame, wrap='word', font=('Georgia', 11),
                                  bg='#ffffff', fg='#333')
            # Scrollbar auf der rechten Seite
            sef_scrollbar = tk.Scrollbar(sef_frame, orient='vertical', command=text_widget.yview)
            text_widget.configure(yscrollcommand=sef_scrollbar.set)
            sef_scrollbar.pack(side='right', fill='y')
            text_widget.pack(side='left', fill='both', expand=True)
            # Rich-Text Formatierung durch Tags
            text_widget.tag_configure('headword', font=font_hebrew, foreground='#000')
            text_widget.tag_configure('pos', font=font_pos_text, foreground='#666')
            text_widget.tag_configure('lex', font=font_small, foreground='#999')
            text_widget.tag_configure('defn', font=font_normal, foreground='#333')
            text_widget.tag_configure('ref', font=font_ref_text, foreground='#888')
            # Füge formatierte Einträge ein
            for idx, entry in enumerate(sefaria_entries, 1):
                headword = entry.get('headword_voweled', entry.get('headword', ''))
                pos = entry.get('pos', '') or entry.get('language', '')
                lexicon = entry.get('lexicon', '')
                lex_text = "Jastrow Dictionary" if "Jastrow" in lexicon else lexicon
                # Kopfzeile: Kopfwort, POS und Lexikon getrennt mit Tags
                if headword:
                    text_widget.insert('end', headword, 'headword')
                if pos:
                    text_widget.insert('end', f" ({pos})", 'pos')
                if lex_text:
                    text_widget.insert('end', f" [{lex_text}]", 'lex')
                text_widget.insert('end', "\n")
                # Definitionen mit Einrückung
                for i, defn in enumerate(entry.get('definitions', []), 1):
                    depth = defn.get('depth', 0)
                    indent = '    ' * depth
                    # Nummerierung nur beim ersten Eintrag pro Ebene anzeigen
                    text_widget.insert('end', f"{indent}{i}. ", 'defn')
                    text_widget.insert('end', defn.get('text', '') + "\n", 'defn')
                # Referenzen
                refs = entry.get('refs', [])
                if refs:
                    refs_text = ", ".join(refs[:5])
                    if len(refs) > 5:
                        refs_text += f" (+{len(refs) - 5})"
                    text_widget.insert('end', "References: ", 'ref')
                    text_widget.insert('end', refs_text + "\n", 'ref')
                # Leerzeile zwischen Einträgen
                text_widget.insert('end', "\n")
            text_widget.configure(state='disabled')
            # Kontext-Menü für Kopieren und Übersetzen
            context_menu = tk.Menu(text_widget, tearoff=0)
            context_menu.add_command(label="Kopieren", 
                                    command=lambda: self._copy_selection(text_widget, status_var))
            context_menu.add_command(label="Auswahl übersetzen (API)", 
                                    command=lambda: self._translate_selection_api(text_widget, status_var))
            def show_menu(event):
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
            text_widget.bind('<Button-3>', show_menu)
            text_widget.bind('<Control-c>', lambda e: self._copy_selection(text_widget, status_var))
        
        # === LOKALE UEBERSETZUNGEN ===
        if not sefaria_entries and translations:
            local_frame = tk.Frame(content_frame, bg='#ffffff', pady=10)
            local_frame.pack(fill='x', anchor='w')
            
            header_line = tk.Frame(local_frame, bg='#ffffff')
            header_line.pack(fill='x', anchor='w')
            
            tk.Label(header_line, text=word, font=font_hebrew, bg='#ffffff', fg='#000').pack(side='left')
            tk.Label(header_line, text="(Lokales Woerterbuch)", font=font_italic, 
                    bg='#ffffff', fg='#666').pack(side='left', padx=10)
            
            for i, (de, en, tractate) in enumerate(translations, 1):
                def_frame = tk.Frame(local_frame, bg='#ffffff', pady=3)
                def_frame.pack(fill='x', anchor='w', padx=20)
                
                tk.Label(def_frame, text=f"{i}.", font=font_normal, bg='#ffffff', 
                        fg='#666', width=3, anchor='e').pack(side='left')
                
                text_frame = tk.Frame(def_frame, bg='#ffffff')
                text_frame.pack(side='left', fill='x')
                
                tk.Label(text_frame, text=de, font=font_normal, bg='#ffffff', fg='#000',
                        wraplength=600, justify='left').pack(anchor='w')
                tk.Label(text_frame, text=en, font=font_italic, bg='#ffffff', fg='#555',
                        wraplength=600, justify='left').pack(anchor='w')
                
                tk.Label(def_frame, text=f"[{tractate}]", font=font_small,
                        bg='#ffffff', fg='#999').pack(side='right')
        
        # === QUELLEN ===
        if sources:
            sources_frame = tk.Frame(content_frame, bg='#ffffff', pady=15)
            sources_frame.pack(fill='x', anchor='w')
            
            tk.Frame(sources_frame, bg='#ddd', height=1).pack(fill='x', pady=10)
            tk.Label(sources_frame, text="Quellen & Kontext", font=font_title,
                    bg='#ffffff', fg='#333').pack(anchor='w')
            
            for src in sources:
                src_frame = tk.Frame(sources_frame, bg='#f9f9f9', pady=8, padx=10)
                src_frame.pack(fill='x', pady=5)
                
                tk.Label(src_frame, text=f"{src['path_str']} (Zeile {src['line']})",
                        font=font_small, bg='#f9f9f9', fg='#4CAF50').pack(anchor='w')
                
                context = src['context'][:400] + ('...' if len(src['context']) > 400 else '')
                tk.Label(src_frame, text=context, font=font_hebrew_small, bg='#f9f9f9',
                        fg='#333', wraplength=700, justify='right', anchor='e').pack(anchor='e', fill='x')
        
        # === KEINE ERGEBNISSE ===
        if not sefaria_entries and not translations and not sources and not user_entries:
            no_result = tk.Frame(content_frame, bg='#fff3cd', pady=20, padx=20)
            no_result.pack(fill='x', pady=20)
            
            tk.Label(no_result, text="Keine Eintraege gefunden", font=font_title,
                    bg='#fff3cd', fg='#856404').pack()
            tk.Label(no_result, text="Versuche 'Aktualisieren' oder 'API Uebersetzen'.",
                    font=font_normal, bg='#fff3cd', fg='#856404').pack()
        
        # === STATUSBAR ===
        status_frame = tk.Frame(win, bg='#f5f5f5', pady=8)
        status_frame.pack(fill='x', side='bottom')
        
        tk.Label(status_frame, textvariable=status_var, font=font_small,
                bg='#f5f5f5', fg='#4CAF50').pack(side='left', padx=15)
        
        stats = f"{len(sefaria_entries)} Sefaria | {len(translations)} lokal | {len(user_entries)} eigene | {len(translated_entries)} Übersetzungen | {len(sources)} Quellen | Gematria: {gematria}"
        tk.Label(status_frame, text=stats, font=font_small, bg='#f5f5f5', fg='#888').pack(side='right', padx=15)
        
        win.bind('<Escape>', lambda e: win.destroy())
        win.focus_force()
        win.lift()
    
    def _render_sefaria_entry(self, parent: tk.Frame, entry: dict, index: int):
        """Rendert Sefaria-Eintrag im Sefaria-Style"""
        font_hebrew = ('David', 16)
        font_pos = ('Georgia', 11, 'italic')
        font_def = ('Georgia', 11)
        font_small = ('Georgia', 9)
        font_ref = ('Georgia', 9, 'italic')
        
        entry_frame = tk.Frame(parent, bg='#ffffff', pady=10)
        entry_frame.pack(fill='x', anchor='w')
        
        if index > 1:
            tk.Frame(entry_frame, bg='#eee', height=1).pack(fill='x', pady=(0, 10))
        
        # Kopfzeile
        header_line = tk.Frame(entry_frame, bg='#ffffff')
        header_line.pack(fill='x', anchor='w')
        
        headword = entry.get('headword_voweled', entry.get('headword', ''))
        tk.Label(header_line, text=headword, font=font_hebrew, bg='#ffffff', fg='#000').pack(side='left')
        
        if index > 0:
            tk.Label(header_line, text=f" {index}", font=('Georgia', 8),
                    bg='#ffffff', fg='#666').pack(side='left', anchor='n')
        
        pos = entry.get('pos', '') or entry.get('language', '')
        if pos:
            tk.Label(header_line, text=f"({pos})", font=font_pos,
                    bg='#ffffff', fg='#666').pack(side='left', padx=8)
        
        lexicon = entry.get('lexicon', '')
        if lexicon:
            lex_text = "Jastrow Dictionary" if "Jastrow" in lexicon else lexicon
            tk.Label(header_line, text=lex_text, font=font_small,
                    bg='#ffffff', fg='#999').pack(side='right')
        
        # Definitionen
        for i, defn in enumerate(entry.get('definitions', []), 1):
            def_frame = tk.Frame(entry_frame, bg='#ffffff', pady=2)
            def_frame.pack(fill='x', anchor='w', padx=15)
            
            depth = defn.get('depth', 0)
            indent = depth * 20
            
            tk.Label(def_frame, text=f"{i}.", font=font_def, bg='#ffffff',
                    fg='#666', width=3, anchor='e').pack(side='left', padx=(indent, 5))
            
            tk.Label(def_frame, text=defn.get('text', ''), font=font_def,
                    bg='#ffffff', fg='#333', wraplength=650, justify='left',
                    anchor='w').pack(side='left', fill='x')
        
        # Referenzen
        refs = entry.get('refs', [])
        if refs:
            ref_frame = tk.Frame(entry_frame, bg='#ffffff', pady=5)
            ref_frame.pack(fill='x', anchor='w', padx=15)
            
            refs_text = ", ".join(refs[:5])
            if len(refs) > 5:
                refs_text += f" (+{len(refs)-5})"
            
            tk.Label(ref_frame, text=f"References: {refs_text}",
                    font=font_ref, bg='#ffffff', fg='#888').pack(anchor='w')
    
    def _format_full_entry(self, word: str, search_result: dict) -> str:
        lines = [f"=== {word} ===", f"Gematria: {self._calculate_gematria(word)}", ""]
        
        for entry in search_result.get('sefaria_entries', []):
            lines.append(f"\n{entry.get('headword', '')} ({entry.get('pos', '')})")
            lines.append(f"[{entry.get('lexicon', '')}]")
            for i, d in enumerate(entry.get('definitions', []), 1):
                lines.append(f"  {i}. {d.get('text', '')}")
        
        if search_result['translations']:
            lines.append("\n--- Lokales Woerterbuch ---")
            for de, en, tract in search_result['translations']:
                lines.append(f"DE: {de}")
                lines.append(f"EN: {en}")
                lines.append(f"[{tract}]")
        
        return '\n'.join(lines)

    # ==================== Hilfsfunktionen ====================
    def _get_original_text(self, word: str) -> str:
        """
        Liefert den zusammengefassten Originaltext der Jastrow‑Einträge für ein Wort.
        Falls kein Eintrag gefunden wird, wird das Wort selbst zurückgegeben.
        """
        try:
            word_clean = self._remove_niqqud(word)
            entries = []
            if word_clean in self.sefaria_entries:
                entries = self.sefaria_entries[word_clean].get('entries', [])
            # Fallback: Wenn noch keine Einträge existieren, versuche via API
            if not entries:
                data = self.sefaria_api.lookup_word(word)
                if data:
                    entries = [SefariaEntryFormatter.format_entry(e) for e in data]
            parts = []
            for entry in entries:
                for d in entry.get('definitions', []):
                    text = d.get('text', '')
                    if text:
                        parts.append(text)
            if parts:
                # Beschränke Länge für API
                combined = '\n'.join(parts)
                return combined[:2000]
        except Exception:
            pass
        return word
    
    # ==================== Dialoge ====================
    
    def _show_api_translation_dialog(self, word: str, parent, status_var):
        if not self.config.get('openai_api_key'):
            messagebox.showwarning("API-Key fehlt", "Bitte zuerst OpenAI API-Key eingeben!")
            self._show_api_settings()
            return
        
        dialog = tk.Toplevel(parent)
        dialog.title("API Uebersetzung")
        # Größeres Übersetzungsfenster
        dialog.geometry("550x360")
        dialog.configure(bg='#ffffff')
        dialog.transient(parent)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"Uebersetze: {word}", font=('David', 16, 'bold'),
                bg='#ffffff', fg='#333').pack(pady=(20, 10))

        # Intelligente Übersetzungsvorschläge: sammle vorhandene Übersetzungen
        suggestions = []
        try:
            # Benutzerwörterbuch (DE/EN)
            for entry in self.user_dictionary.get_entries(word):
                if entry.get('de'):
                    suggestions.append(entry['de'])
                if entry.get('en'):
                    suggestions.append(entry['en'])
            # Sefaria‑Übersetzungswörterbuch
            for entry in self.sefaria_translation_dict.get_entries(word) or []:
                t = entry.get('translation')
                if t:
                    suggestions.append(t)
            # Entferne Duplikate und leere Einträge
            suggestions = [s.strip() for s in suggestions if s and s.strip()]
            suggestions = list(dict.fromkeys(suggestions))  # Reihenfolge bewahren
        except Exception:
            suggestions = []

        if suggestions:
            # Rahmen für Vorschläge
            sugg_frame = tk.Frame(dialog, bg='#ffffff')
            sugg_frame.pack(fill='x', padx=20, pady=(0, 10))
            tk.Label(sugg_frame, text="Vorschläge:", font=('Georgia', 9, 'italic'),
                     bg='#ffffff', fg='#666').pack(anchor='w')
            # Zeige nur die ersten fünf Vorschläge an
            for s in suggestions[:5]:
                lbl = tk.Label(sugg_frame, text=f"• {s}", font=('Georgia', 11),
                               bg='#f7f7f7', fg='#333', anchor='w', justify='left')
                lbl.pack(fill='x', padx=5, pady=1)
        
        tk.Label(dialog, text="Zielsprache:", font=('Georgia', 10),
                bg='#ffffff', fg='#666').pack()
        
        lang_var = tk.StringVar(value=self.config.get('translation_language', 'de'))
        btn_frame = tk.Frame(dialog, bg='#ffffff')
        btn_frame.pack(pady=10)
        
        tk.Radiobutton(btn_frame, text="Deutsch", variable=lang_var, value='de',
                      bg='#ffffff', font=('Georgia', 11)).pack(side='left', padx=20)
        tk.Radiobutton(btn_frame, text="English", variable=lang_var, value='en',
                      bg='#ffffff', font=('Georgia', 11)).pack(side='left', padx=20)
        
        # Ergebnisrahmen mit Scrollbar für die Übersetzung
        result_frame = tk.Frame(dialog, bg='#ffffff')
        result_frame.pack(fill='both', expand=False, padx=20, pady=10)
        result_scrollbar = tk.Scrollbar(result_frame, orient='vertical')
        result_scrollbar.pack(side='right', fill='y')
        result_text = tk.Text(result_frame, wrap='word', font=('Georgia', 11),
                              bg='#fafafa', fg='#1565C0', height=6, width=60)
        result_text.pack(side='left', fill='both', expand=True)
        result_text.configure(state='disabled')
        result_text.configure(yscrollcommand=result_scrollbar.set)
        result_scrollbar.config(command=result_text.yview)
        
        def do_translate():
            lang = lang_var.get()
            # Statusanzeige im Ergebnisfeld
            result_text.config(state='normal')
            result_text.delete('1.0', 'end')
            result_text.insert('1.0', "Übersetze...")
            result_text.config(state='disabled')
            dialog.update()

            def translate():
                # Hole den originalen Jastrow‑Text für das Wort
                original_text = self._get_original_text(word)
                source_text = original_text or word
                # Prüfe, ob bereits eine Übersetzung existiert
                # Berücksichtige das Übersetzungs‑Cache‑Fenster aus der Konfiguration
                max_age = self.config.get('translation_cache_days', 0)
                existing = self.translation_store.get_translations(source_text, max_age_days=max_age)
                if existing:
                    translation = existing[0].get('translation')
                else:
                    translation = self._translate_with_openai(source_text, lang)
                def update():
                    if translation:
                        # Zeige Übersetzung im Textfeld
                        result_text.config(state='normal')
                        result_text.delete('1.0', 'end')
                        result_text.insert('1.0', translation)
                        result_text.config(state='disabled')
                        # Speichere Übersetzung in Historie
                        self.query_history.update_api_translation(word, translation, lang)
                        # Speichere in Sefaria-Übersetzungswörterbuch (Originaltext und Übersetzung)
                        try:
                            self.sefaria_translation_dict.add_entry(word, source_text, translation)
                        except Exception:
                            pass
                        # Speichere in globalem Übersetzungsspeicher
                        if not existing:
                            try:
                                self.translation_store.add_translation(source_text, translation, word)
                            except Exception:
                                pass
                        def copy_close():
                            pyperclip.copy(translation)
                            status_var.set("Uebersetzung kopiert!")
                            parent.after(2000, lambda: status_var.set(""))
                            dialog.destroy()
                        tk.Button(dialog, text="Kopieren & Schliessen", command=copy_close,
                                 bg='#4CAF50', fg='white', font=('Georgia', 10),
                                 relief='flat', padx=15).pack(pady=5)
                    else:
                        result_text.config(state='normal')
                        result_text.delete('1.0', 'end')
                        result_text.insert('1.0', "Übersetzung fehlgeschlagen!")
                        # Rot einfärben
                        result_text.tag_configure('error', foreground='#f44336')
                        result_text.tag_add('error', '1.0', 'end')
                        result_text.config(state='disabled')
                dialog.after(0, update)
            threading.Thread(target=translate, daemon=True).start()
        
        tk.Button(dialog, text="Uebersetzen", command=do_translate,
                 bg='#FF9800', fg='white', font=('Georgia', 11),
                 relief='flat', padx=20, pady=5).pack(pady=10)
    
    def _show_add_to_dict_dialog(self, word: str, translations: List[Tuple], parent):
        dialog = tk.Toplevel(parent)
        dialog.title("Zum Woerterbuch hinzufuegen")
        dialog.geometry("500x350")
        dialog.configure(bg='#ffffff')
        dialog.transient(parent)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"Wort: {word}", font=('David', 18, 'bold'),
                bg='#ffffff', fg='#333').pack(pady=(20, 15))
        
        default_de = translations[0][0] if translations else ""
        default_en = translations[0][1] if translations else ""
        
        tk.Label(dialog, text="Deutsche Uebersetzung:", font=('Georgia', 10),
                bg='#ffffff', fg='#666').pack(anchor='w', padx=20)
        de_entry = tk.Entry(dialog, font=('Georgia', 11), width=50)
        de_entry.pack(padx=20, pady=5)
        de_entry.insert(0, default_de)
        
        tk.Label(dialog, text="English Translation:", font=('Georgia', 10),
                bg='#ffffff', fg='#666').pack(anchor='w', padx=20)
        en_entry = tk.Entry(dialog, font=('Georgia', 11), width=50)
        en_entry.pack(padx=20, pady=5)
        en_entry.insert(0, default_en)
        
        tk.Label(dialog, text="Notizen:", font=('Georgia', 10),
                bg='#ffffff', fg='#666').pack(anchor='w', padx=20)
        notes_entry = tk.Entry(dialog, font=('Georgia', 11), width=50)
        notes_entry.pack(padx=20, pady=5)
        
        def save():
            de = de_entry.get().strip()
            en = en_entry.get().strip()
            if not de and not en:
                messagebox.showwarning("Fehler", "Mindestens eine Uebersetzung eingeben!")
                return
            self.user_dictionary.add_entry(word, de, en, notes_entry.get().strip())
            messagebox.showinfo("Gespeichert", f"'{word}' hinzugefuegt!")
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg='#ffffff')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Speichern", command=save,
                 bg='#4CAF50', fg='white', font=('Georgia', 11),
                 relief='flat', padx=20, pady=5).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Abbrechen", command=dialog.destroy,
                 bg='#666', fg='white', font=('Georgia', 11),
                 relief='flat', padx=20, pady=5).pack(side='left', padx=10)
    
    def _show_api_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Einstellungen")
        win.geometry("550x400")
        win.configure(bg='#1e1e1e')
        
        font_normal = ('Segoe UI', 10)
        font_small = ('Segoe UI', 9)
        
        tk.Label(win, text="OpenAI API-Key:", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(20, 5))
        
        api_var = tk.StringVar(value=self.config.get('openai_api_key', ''))
        api_entry = tk.Entry(win, textvariable=api_var, font=font_normal, width=55,
                            show='*', bg='#2d2d2d', fg='#e0e0e0', insertbackground='white')
        api_entry.pack(padx=20, pady=5)
        
        def toggle():
            api_entry.config(show='' if api_entry.cget('show') == '*' else '*')
        tk.Button(win, text="Anzeigen/Verstecken", command=toggle,
                 bg='#3a3a3a', fg='#e0e0e0', font=font_small, relief='flat').pack(anchor='w', padx=20)
        
        tk.Label(win, text="Uebersetzungssprache:", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(15, 5))
        
        lang_var = tk.StringVar(value=self.config.get('translation_language', 'de'))
        lang_frame = tk.Frame(win, bg='#1e1e1e')
        lang_frame.pack(anchor='w', padx=20)
        tk.Radiobutton(lang_frame, text="Deutsch", variable=lang_var, value='de',
                      bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3a3a3a').pack(side='left', padx=10)
        tk.Radiobutton(lang_frame, text="English", variable=lang_var, value='en',
                      bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3a3a3a').pack(side='left', padx=10)
        
        tk.Label(win, text="API-Modell:", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(15, 5))
        
        model_var = tk.StringVar(value=self.config.get('api_model', 'gpt-4o-mini'))
        model_frame = tk.Frame(win, bg='#1e1e1e')
        model_frame.pack(anchor='w', padx=20)
        tk.Radiobutton(model_frame, text="GPT-4o-mini", variable=model_var, value='gpt-4o-mini',
                      bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3a3a3a', font=font_small).pack(side='left', padx=5)
        tk.Radiobutton(model_frame, text="GPT-3.5-turbo", variable=model_var, value='gpt-3.5-turbo',
                      bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3a3a3a', font=font_small).pack(side='left', padx=5)
        
        tk.Label(win, text="Sefaria:", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(15, 5))
        
        sefaria_var = tk.BooleanVar(value=self.config.get('sefaria_enabled', True))
        tk.Checkbutton(win, text="Sefaria API aktivieren", variable=sefaria_var,
                      bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3a3a3a', font=font_small).pack(anchor='w', padx=30)

        # Konfigurierbare Cache‑Dauer für Sefaria
        tk.Label(win, text="Sefaria‑Cache (Tage):", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(10, 2))
        cache_var = tk.StringVar(value=str(self.config.get('sefaria_cache_days', 7)))
        tk.Entry(win, textvariable=cache_var, width=5, font=font_normal,
                 bg='#2d2d2d', fg='#e0e0e0', insertbackground='white').pack(anchor='w', padx=30, pady=(0, 10))

        # Konfigurierbare Cache‑Dauer für Übersetzungen
        tk.Label(win, text="Übersetzungen erneuern nach (Tage):", font=font_normal,
                bg='#1e1e1e', fg='#e0e0e0').pack(anchor='w', padx=20, pady=(2, 2))
        trans_cache_var = tk.StringVar(value=str(self.config.get('translation_cache_days', 0)))
        tk.Entry(win, textvariable=trans_cache_var, width=5, font=font_normal,
                 bg='#2d2d2d', fg='#e0e0e0', insertbackground='white').pack(anchor='w', padx=30, pady=(0, 10))
        
        def save():
            self.config['openai_api_key'] = api_var.get().strip()
            self.config['translation_language'] = lang_var.get()
            self.config['api_model'] = model_var.get()
            self.config['sefaria_enabled'] = sefaria_var.get()
            # Lese Cache‑Dauern aus Eingabefeldern
            try:
                sef_days = int(cache_var.get())
            except Exception:
                sef_days = self.config.get('sefaria_cache_days', 7)
            try:
                trans_days = int(trans_cache_var.get())
            except Exception:
                trans_days = self.config.get('translation_cache_days', 0)
            self.config['sefaria_cache_days'] = sef_days
            self.config['translation_cache_days'] = trans_days
            self.sefaria_api.cache_days = sef_days
            self.config['sefaria_enabled'] = sefaria_var.get()
            self.sefaria_api.enabled = sefaria_var.get()
            self._save_config()
            win.destroy()
            messagebox.showinfo("Gespeichert", "Einstellungen gespeichert!")
        
        btn_frame = tk.Frame(win, bg='#1e1e1e')
        btn_frame.pack(fill='x', pady=30, padx=20)
        tk.Button(btn_frame, text="Speichern", command=save, bg='#4CAF50', fg='white',
                 font=font_normal, relief='flat', padx=20, pady=5).pack(side='right', padx=5)
        tk.Button(btn_frame, text="Abbrechen", command=win.destroy, bg='#666', fg='white',
                 font=font_normal, relief='flat', padx=20, pady=5).pack(side='right', padx=5)
    
    def _show_history_window(self):
        win = tk.Toplevel(self.root)
        win.title("Abfrage-Historie")
        win.geometry("950x600")
        win.configure(bg='#ffffff')
        
        stats = self.query_history.get_stats()
        tk.Label(win, text=f"Gespeicherte Woerter: {stats.get('unique_words', 0)} | Gesamt-Abfragen: {stats.get('total_queries', 0)}",
                font=('Georgia', 9), bg='#f5f5f5', fg='#666', pady=8).pack(fill='x')
        
        search_frame = tk.Frame(win, bg='#ffffff', pady=10)
        search_frame.pack(fill='x', padx=15)
        tk.Label(search_frame, text="Suchen:", font=('Georgia', 10), bg='#ffffff').pack(side='left')
        search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=search_var, font=('Georgia', 10), width=40).pack(side='left', padx=10)
        
        tree_frame = tk.Frame(win, bg='#ffffff')
        tree_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        columns = ('word', 'gematria', 'sefaria', 'local', 'api', 'count')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        tree.heading('word', text='Wort')
        tree.heading('gematria', text='Gematria')
        tree.heading('sefaria', text='Sefaria')
        tree.heading('local', text='Lokal')
        tree.heading('api', text='API-Uebersetzung')
        tree.heading('count', text='Anzahl')
        
        tree.column('word', width=100, anchor='e')
        tree.column('gematria', width=70, anchor='center')
        tree.column('sefaria', width=60, anchor='center')
        tree.column('local', width=200, anchor='w')
        tree.column('api', width=300, anchor='w')
        tree.column('count', width=60, anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def populate(entries):
            for item in tree.get_children():
                tree.delete(item)
            for entry in entries:
                word = entry.get('word', '')
                gematria = entry.get('gematria', 0)
                sefaria = entry.get('sefaria_count', 0)
                
                local = ""
                for t in entry.get('translations', [])[:1]:
                    local = t.get('de', '')[:40]
                
                api = ""
                if entry.get('api_translations'):
                    for lang, trans in entry['api_translations'].items():
                        api = trans.get('text', '')[:50]
                        break
                
                count = entry.get('query_count', 1)
                tree.insert('', 'end', values=(word, gematria, sefaria, local, api, count))
        
        populate(self.query_history.get_history(200))
        
        def on_search(*args):
            q = search_var.get()
            populate(self.query_history.search_history(q) if q else self.query_history.get_history(200))
        
        search_var.trace('w', on_search)
        
        def on_double_click(event):
            sel = tree.selection()
            if sel:
                word = tree.item(sel[0])['values'][0]
                self.show_tooltip(word, self.search_word(word))
        
        tree.bind('<Double-1>', on_double_click)
        
        tk.Button(win, text="Schliessen", command=win.destroy,
                 bg='#2196F3', fg='white', font=('Georgia', 10),
                 relief='flat', padx=20).pack(pady=10)

    # ==================== Wörterbuch anzeigen ====================
    def _show_jastrow_dictionary_window(self):
        """
        Öffnet ein Fenster, das alle gespeicherten Jastrow‑Einträge (einzelne
        Wörter) anzeigt. Die Liste kann gefiltert werden. Durch Doppelklick
        auf ein Wort wird dessen Tooltip geöffnet (mit allen Informationen
        wie im Hauptprogramm). Das Wörterbuch wird automatisch alphabetisch
        sortiert und unterstützt Scrollen.
        """
        win = tk.Toplevel(self.root)
        win.title("Jastrow Wörterbuch")
        win.geometry("700x600")
        win.configure(bg='#ffffff')

        # Suchleiste
        search_frame = tk.Frame(win, bg='#ffffff', pady=10)
        search_frame.pack(fill='x', padx=15)
        tk.Label(search_frame, text="Suchen:", font=('Georgia', 10), bg='#ffffff').pack(side='left')
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=('Georgia', 10), width=40)
        search_entry.pack(side='left', padx=10)

        # Liste der Wörter
        list_frame = tk.Frame(win, bg='#ffffff')
        list_frame.pack(fill='both', expand=True, padx=15, pady=10)

        scrollbar = tk.Scrollbar(list_frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')

        listbox = tk.Listbox(list_frame, font=('David', 16), activestyle='none')
        listbox.pack(side='left', fill='both', expand=True)
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        # Lade alle gespeicherten Wörter (aleph‑bet sortiert)
        all_words = self.jastrow_dict.get_all_entries()

        def populate(filter_str: str = ''):
            listbox.delete(0, 'end')
            for w, fname in all_words:
                # Filtere Wörter, die hochgestellte Ziffern oder reguläre Ziffern enthalten
                # Solche Kopfwoerter sind typischerweise Varianten ohne eigenen Eintrag
                if re.search(r'[0-9²³¹⁰-⁹]', w):
                    continue
                if filter_str and filter_str not in self._remove_niqqud(w):
                    continue
                listbox.insert('end', w)

        populate()

        def on_search(*args):
            q = search_var.get().strip()
            populate(self._remove_niqqud(q))

        search_var.trace('w', on_search)

        # Doppelklick: Tooltip öffnen
        def on_double_click(event):
            selection = listbox.curselection()
            if selection:
                word = listbox.get(selection[0])
                self.show_tooltip(word, self.search_word(word))

        listbox.bind('<Double-1>', on_double_click)
        # Schliessen Button
        tk.Button(win, text="Schliessen", command=win.destroy,
                 bg='#2196F3', fg='white', font=('Georgia', 10), relief='flat', padx=20).pack(pady=10)

    # ==================== Kontextmenü-Funktionen ====================
    def _copy_selection(self, text_widget, status_var):
        """Kopiert den aktuell markierten Text aus dem Text-Widget"""
        try:
            text_widget.config(state='normal')
            selected = text_widget.get('sel.first', 'sel.last')
            text_widget.config(state='disabled')
            if selected:
                pyperclip.copy(selected)
                status_var.set("Kopiert!")
                # Status nach 2 Sekunden zurücksetzen
                text_widget.after(2000, lambda: status_var.set(""))
        except tk.TclError:
            pass

    def _translate_selection_api(self, text_widget, status_var):
        """Übersetzt den aktuell markierten Text mit der OpenAI‑API"""
        try:
            text_widget.config(state='normal')
            selected = text_widget.get('sel.first', 'sel.last')
            text_widget.config(state='disabled')
            if not selected:
                return
            if not self.config.get('openai_api_key'):
                messagebox.showwarning("API-Key fehlt", 
                    "Bitte zuerst OpenAI API-Key in den Einstellungen eingeben!")
                return
            status_var.set("Übersetze…")
            # Starte Übersetzung in separatem Thread
            def translate():
                lang = self.config.get('translation_language', 'de')
                # Prüfe, ob bereits eine Übersetzung existiert
                # Berücksichtige das Übersetzungs‑Cache‑Fenster aus der Konfiguration
                max_age = self.config.get('translation_cache_days', 0)
                existing = self.translation_store.get_translations(selected, max_age_days=max_age)
                translation = None
                if existing:
                    # Verwende die erste gespeicherte Übersetzung
                    translation = existing[0].get('translation')
                else:
                    translation = self._translate_with_openai(selected, lang)
                def show_result():
                    if translation:
                        # Speichere ggf. neue Übersetzung im Store
                        if not existing:
                            try:
                                # Die aktuelle Auswahl gehört zu keinem spezifischen Wort – verwende
                                # den Inhalt selbst als „word" für Speicherung.
                                self.translation_store.add_translation(selected, translation, selected)
                            except Exception:
                                pass
                        # Zeige Übersetzung in neuem Fenster
                        res_win = tk.Toplevel(self.root)
                        res_win.title("Übersetzung")
                        res_win.geometry("500x260")
                        res_win.configure(bg='#f5f5f5')
                        # Originaltext
                        tk.Label(res_win, text="Original:", font=('Georgia', 10, 'bold'),
                                 bg='#f5f5f5', fg='#333').pack(anchor='w', padx=15, pady=(15,5))
                        orig_text = tk.Text(res_win, height=4, wrap='word', font=('Georgia', 11),
                                            bg='#fafafa', fg='#333')
                        orig_text.pack(fill='x', padx=15, pady=5)
                        orig_text.insert('1.0', selected)
                        orig_text.configure(state='disabled')
                        # Übersetzungstitel
                        lang_name = "Deutsch" if lang == 'de' else "English"
                        tk.Label(res_win, text=f"{lang_name} Übersetzung:", font=('Georgia', 10, 'bold'),
                                 bg='#f5f5f5', fg='#333').pack(anchor='w', padx=15, pady=(10,5))
                        # Frame für Text mit Scrollbar
                        tf = tk.Frame(res_win, bg='#f5f5f5')
                        tf.pack(fill='both', expand=True, padx=15, pady=(0,10))
                        sbar = tk.Scrollbar(tf, orient='vertical')
                        sbar.pack(side='right', fill='y')
                        trans_text = tk.Text(tf, wrap='word', font=('Georgia', 11),
                                            bg='#fafafa', fg='#333', height=6)
                        trans_text.pack(side='left', fill='both', expand=True)
                        trans_text.configure(yscrollcommand=sbar.set)
                        sbar.config(command=trans_text.yview)
                        trans_text.insert('1.0', translation)
                        trans_text.configure(state='disabled')
                        # Schliessen-Button
                        tk.Button(res_win, text="Schliessen", command=res_win.destroy,
                                 bg='#2196F3', fg='white', font=('Georgia', 10), relief='flat', padx=20).pack(pady=10)
                        status_var.set("")
                    else:
                        status_var.set("Übersetzung fehlgeschlagen!")
                        text_widget.after(3000, lambda: status_var.set(""))
                # Nach Abschluss der Übersetzung im Hauptthread ausführen
                text_widget.after(0, show_result)
            # Starte Worker‑Thread für die Übersetzung
            threading.Thread(target=translate, daemon=True).start()
        except tk.TclError:
            pass

    # ==================== Bulk‑Laden von Sefaria‑Einträgen ====================
    def bulk_preload_sefaria_from_text(self, text: str) -> int:
        """
        Lädt anhand eines beliebigen Textes alle darin enthaltenen
        hebräischen Wörter vorab aus der Sefaria‑API. Für jedes gefundene
        Wort wird eine API‑Abfrage durchgeführt, der Eintrag formatiert
        und im lokalen Wörterbuch gespeichert. Bereits vorhandene
        Einträge werden übersprungen. Die Methode liefert die Anzahl der
        untersuchten Wörter zurück.

        Hinweis: Dieses Verfahren kann viele API‑Abfragen auslösen. Bei
        großen Texten sollte daher ein angemessener Abstand zwischen den
        Abfragen eingehalten werden oder das Feature nur bei aktivierter
        Internetverbindung genutzt werden.
        """
        # Extrahiere hebräische Zeichenfolgen mittels Unicode‑Range
        words = set(re.findall(r'[\u0590-\u05FF]+', text))
        count = 0
        for w in words:
            # Bereinigtes Wort ohne Nikud zum Vergleich
            clean = self._remove_niqqud(w)
            if not clean or clean in self.sefaria_entries:
                continue
            # Abfrage bei Sefaria
            data = self.sefaria_api.lookup_word(w)
            if data:
                formatted = []
                for entry in data:
                    try:
                        fmt = SefariaEntryFormatter.format_entry(entry)
                        formatted.append(fmt)
                        # Fügt vollständigen Eintrag ins Wörterbuch
                        self.jastrow_dict.add_entry(fmt.get('headword', ''), fmt)
                    except Exception:
                        pass
                # Speichere im lokalen Sefaria‑Entries Cache
                if formatted:
                    try:
                        self.sefaria_entries[clean] = {'entries': formatted}
                    except Exception:
                        pass
            count += 1
        return count

    def bulk_preload_sefaria_from_file(self):
        """
        Öffnet einen Dateidialog und lädt die ausgewählte Textdatei. Der
        Inhalt der Datei wird analysiert, und alle darin enthaltenen
        hebräischen Wörter werden über die Sefaria‑API geladen. Nach
        Abschluss erscheint eine Meldung mit der Anzahl der verarbeiteten
        Wörter.
        """
        file_path = filedialog.askopenfilename(title="Textdatei auswählen",
                                               filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gelesen werden: {e}")
            return
        total = self.bulk_preload_sefaria_from_text(text)
        messagebox.showinfo("Fertig", f"{total} Wörter verarbeitet. Lokales Wörterbuch aktualisiert.")
    
    # ==================== Clipboard ====================
    
    def check_clipboard(self):
        if not self.monitoring:
            self.root.after(self.check_interval, self.check_clipboard)
            return
        
        try:
            current = pyperclip.paste()
            
            if current and current != self.last_clipboard:
                if any('\u0590' <= c <= '\u05FF' for c in current):
                    clean = current.strip()
                    if clean:
                        print(f"\n[Strg+C] '{clean}'")
                        result = self.search_word(clean)
                        
                        sef = len(result.get('sefaria_entries', []))
                        loc = len(result['translations'])
                        usr = len(result.get('user_entries', []))
                        src = len(result['sources'])
                        print(f"   -> {sef} Sefaria, {loc} lokal, {usr} eigene, {src} Quellen")
                        
                        self.show_tooltip(clean, result)
                
                self.last_clipboard = current
            
            self.clipboard_errors = 0
        except Exception as e:
            self.clipboard_errors += 1
            if self.clipboard_errors >= 10:
                print(f"[WARNUNG] Clipboard: {e}")
                self.clipboard_errors = 0
        
        self.root.after(self.check_interval, self.check_clipboard)
    
    def create_icon(self):
        width, height = 64, 64
        image = Image.new('RGB', (width, height), color='#2196F3')
        dc = ImageDraw.Draw(image)
        dc.text((width // 2, height // 2), "J", fill='white', anchor='mm')
        
        stats = self.query_history.get_stats()
        
        # System‑Tray‑Menü. Neben den bestehenden Einträgen wird hier das
        # Jastrow‑Wörterbuch angezeigt. Die Anzahl der gespeicherten Wörter
        # wird in Klammern anzeigt, um den Nutzer zu informieren.
        dict_count = len(self.jastrow_dict.get_all_entries())
        # Erstelle Menü dynamisch, damit das Monitoring umgeschaltet werden kann
        def build_menu():
            monitor_label = f'Strg+C Monitoring: {"AKTIV" if self.monitoring else "INAKTIV"}'
            return pystray.Menu(
                item(monitor_label, self.toggle_monitoring),
                item('Letzten Text nachschlagen', self.lookup_last),
                item(f'Historie ({stats.get("unique_words", 0)})', self._show_history_window),
                item(f'Wörterbuch ({dict_count})', self._show_jastrow_dictionary_window),
                # Neues Menüelement: Bulk‑Import aus Textdatei
                item('Bulk Sefaria (Text)', self.bulk_preload_sefaria_from_file),
                item('Einstellungen', self._show_api_settings),
                item('Info', self.show_about),
                item('Beenden', self.quit_app)
            )
        self.icon = pystray.Icon(
            "jastrow", image, "Jastrow Dictionary\nStrg+C = Uebersetzung", build_menu()
        )
    
    def lookup_last(self):
        try:
            text = pyperclip.paste()
            if text and any('\u0590' <= c <= '\u05FF' for c in text):
                self.show_tooltip(text.strip(), self.search_word(text.strip()))
            else:
                messagebox.showinfo("Info", "Kein hebraeischer Text im Clipboard!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def show_about(self):
        stats = self.query_history.get_stats()
        messagebox.showinfo("Jastrow Dictionary", f"""JASTROW DICTIONARY
Sefaria-Style Version

{'=' * 40}

Woerterbuecher: {len(self.tractate_names)}
Sefaria-Cache: {len(self.sefaria_entries)}
Quelldateien: {self.source_index.file_count}
Benutzer-Eintraege: {len(self.user_dictionary.entries)}
Gespeicherte Abfragen: {stats.get('unique_words', 0)}

{'=' * 40}

FEATURES:
- Sefaria-Style Ausgabe
- Sefaria API Integration
- OpenAI API Uebersetzung (DE/EN)
- Eigenes Woerterbuch
- Dauerhafte Speicherung
- Strg+C Monitoring (aktiv)

BENUTZUNG:
1. Hebraeischen Text markieren
2. Strg+C druecken
3. Uebersetzung erscheint!""")
    
    def quit_app(self):
        self.monitoring = False
        if self.icon:
            self.icon.stop()
        self.root.quit()

    # ==================== Monitoring Umschalten ====================
    def toggle_monitoring(self, *args, **kwargs):
        """
        Schaltet das automatische Clipboard‑Monitoring ein oder aus. Nach dem Umschalten
        wird das System‑Tray‑Menü aktualisiert, um den neuen Status anzuzeigen.
        """
        self.monitoring = not self.monitoring
        # Aktualisiere Menüeinträge dynamisch
        if self.icon:
            stats = self.query_history.get_stats()
            dict_count = len(self.jastrow_dict.get_all_entries())
            monitor_label = f'Strg+C Monitoring: {"AKTIV" if self.monitoring else "INAKTIV"}'
            new_menu = pystray.Menu(
                item(monitor_label, self.toggle_monitoring),
                item('Letzten Text nachschlagen', self.lookup_last),
                item(f'Historie ({stats.get("unique_words", 0)})', self._show_history_window),
                item(f'Wörterbuch ({dict_count})', self._show_jastrow_dictionary_window),
                item('Einstellungen', self._show_api_settings),
                item('Info', self.show_about),
                item('Beenden', self.quit_app)
            )
            self.icon.menu = new_menu
    
    def run(self):
        self.load_files()
        self.create_icon()
        self.monitoring = True
        self.check_clipboard()
        
        print("=" * 60)
        print("  JASTROW DICTIONARY - SEFARIA STYLE")
        print("=" * 60)
        print()
        print("  [STRG+C] Hebraeischen Text kopieren = Uebersetzung")
        print("  System Tray Icon aktiv")
        print()
        print("=" * 60)
        
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    app = JastrowDictionary()
    app.run()
