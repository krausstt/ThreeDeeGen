# Türklinke Louis XV für Wand- und Türpaneele

Status: v1, ungedruckt

![Übersicht](out/tuerklinke_louis_overview.png)

## Ziel

Eine dekorative Drückergarnitur mit Langschild, passend zu den Boiserie-Paneelen aus dem Slicer-Projekt des Nutzers (`reference/01_slicer_paneele_screenshot.png`). Sie wird im Slicer direkt auf ein Türpaneel gesetzt und mit ihm als ein Teil gedruckt. Die Klinke ist Deko und nicht beweglich.

**Stil:** Die Paneele haben Akanthus-Kartuschen, C-Voluten und Perlstäbe (Régence / Louis XV). Die Klinke greift das auf:

- Langschild mit geschweiftem Umriss: Fußspitze, unterer Lappen, Taille und Ohren oben
- Perlstab-Rand wie an den Paneelen
- Muschelfächer mit C-Voluten oben, Glockenblumen-Gehänge unter dem Schlüsselloch, Akanthus-Tropfen unten
- Rosette mit Perlring und Kuppel am Hebel
- Hebel „bec de cane“, leicht geschwungen, mit nach unten eingerollter Volute und Knauf

## Maße (gemessen / angenommen)

| Parameter | Wert | Quelle |
|---|---|---|
| Türpaneel im Slicer | ≈ 65 × 150 mm | **ANGENOMMEN**, aus dem Screenshot über das 10-mm-Raster von Bambu Studio geschätzt, ±7 % (Perspektive) |
| Maßstab | ≈ 1:13,3 (150 mm ↔ 2 m Tür) | abgeleitet |
| Vorbild real | Langschild 290 × 74 mm, Drücker 145 mm, Ausladung 66 mm, Entfernung Drücker–Schlüssel 72 mm (DIN 18251 Zimmertür) | übliche Werte, nicht gemessen |
| Modell | Schild 5,6 × 22 mm × 0,8 mm, Hebel 11,5 mm ab Achse, Ausladung 5,75 mm, Schlüsselloch 5,4 mm unter der Achse | `out/tuerklinke_louis_report.json` |
| Gesamt | 14,3 × 22,0 × 5,75 mm, 0,2 g | |

Mit `--door-panel-h <mm>` (tatsächliche Paneelhöhe aus dem Slicer) oder `--size` skaliert alles gleichmäßig. Das ist das Gleiche wie gleichmäßiges Skalieren im Slicer.

## Druckbarkeit

- **Orientierung:** wie die Paneele liegend, z = 0 ist die Türoberfläche. Schild und Ornamente sind reines Aufwärts-Relief.
- **Hebel:** Er schwebt 4,4 mm über der Tür und wäre damit ein 11-mm-Überhang. Darunter steht deshalb ein senkrechter **Steg**, 1,41 × so breit wie der lokale Hebelradius (≥ 1 mm). So trifft er den runden Hebel genau an dessen 45°-Punkten.
  - Unter dem geraden Arm ist der Steg als **Spitzbogen** mit 45°-Flanken geöffnet (7 mm Spannweite), das bleibt stützfrei.
  - Die Tür berühren nur der Hals und die gebogene Wand unter der Volute.
  - Von vorne ist der Steg hinter dem Hebel verborgen. Von der Seite ist er sichtbar, das ist der Preis für einen stützfreien, unzerbrechlichen Hebel.
- **Überhang** 0,7 mm² (Rundungsfacetten), keine Stützen nötig.
- **Kleinste Details** werden im Generator geprüft (`details_ok`, Abbruch bei Unterschreitung):

  | Detail | Maß |
  |---|---|
  | Steg | ≥ 0,99 mm |
  | Hebel | ≥ Ø 1,04 mm |
  | Perlen | Ø 0,66 mm |
  | Schlüsselloch-Schlitz | 0,52 mm |
  | Schild | 0,8 mm |

  - Bei 0,4-mm-Düse also **nicht unter ≈ 90 % skalieren**.
  - Perlen und Muschelrippen werden mit 0,4 mm eher Textur als scharfes Detail. Mit 0,2-mm-Düse deutlich feiner.
- **Empfehlung:** 0,08–0,12 mm Schichthöhe für die Ornamente. Für Zierteile wie diese bietet Bambu Studio eine variable Schichthöhe.

## Im Slicer platzieren (Bambu Studio)

1. Paneel-Objekt rechtsklicken → **Teil hinzufügen → Laden** → `tuerklinke_louis_rechts.stl` oder `_links.stl`.
   - Als Teil desselben Objekts werden Klinke und Paneel als ein Körper verschmolzen gedruckt.
   - Ich habe nicht geprüft, wo Bambu Studio ein hinzugefügtes Teil in z ablegt.
2. **z-Position** der Klinke auf die Höhe der Paneeloberfläche an dieser Stelle setzen, **minus 0,2 mm**. Dann sitzt die Unterseite sicher im Paneel statt nur aufzuliegen.
3. **Lage auf der Tür:**
   - Höhe: Drückerachse etwa 79 mm über der Paneel-Unterkante. Real sind das 1 050 mm.
   - Waagerecht: Schild mittig zwischen dem Perlstab am Rand und der inneren Profilleiste, dort ist laut Screenshot ≈ 7 mm Platz.
   - Der Hebel zeigt zur Türmitte und darf über die Profilleiste ragen, der Steg verschmilzt dann mit ihr.
4. **rechts** = Hebel zeigt nach rechts, also für das linke Türfries (Band rechts). **links** ist gespiegelt.

## Dateien (`out/`)

| Datei | Inhalt |
|---|---|
| `tuerklinke_louis_rechts.stl` / `.3mf` | Hebel nach rechts (+x) |
| `tuerklinke_louis_links.stl` / `.3mf` | gespiegelt |
| `tuerklinke_louis_probe.3mf` | beide Klinken auf einem 40 × 30 × 1,2-mm-Probeblock, kurzer Testdruck für Größe und Detail (Druckzeit nicht ermittelt) |
| `tuerklinke_louis_report.json` | Maße, Detailprüfung, Druckbarkeitsberichte |

```bash
python3 projects/tuerklinke-louis/generate.py                         # Standard (Paneel 150 mm)
python3 projects/tuerklinke-louis/generate.py --door-panel-h 162      # an die echte Paneelhöhe anpassen
python3 projects/tuerklinke-louis/preview.py                          # Übersichtsbild
```

## Offene Fragen

- Exakte Höhe des Türpaneels im Slicer (Objektmaße in Bambu Studio)? Die Klinke ist ein Schätzwert ±7 %.
- Welches Paneel ist die Tür, und auf welcher Seite sitzt das Band? Daraus folgt links oder rechts.
- Soll sie farblich abgesetzt werden (Messing/Gold)? Dann wäre ein Filamentwechsel über die z-Höhe oder ein AMS-Farbwechsel sinnvoll. Falls ein AMS lite vorhanden ist, ginge das als Teil mit eigener Farbe.
