# Untis-Kalender-Sync

Holt deinen persönlichen Stundenplan (inklusive Vertretungen und Ausfällen)
über die WebUntis-JSON-RPC-API und erzeugt daraus eine `calendar.ics`.
Ein GitHub-Actions-Workflow aktualisiert die Datei automatisch alle 2 Stunden;
Apple Kalender (oder Google/Outlook) abonniert die URL und hält sich damit
selbst aktuell.

Das Skript nutzt nur die Python-Standardbibliothek — kein `pip install` nötig.

## Lokal testen (ohne GitHub)

1. Öffne im VS-Code-Explorer die Datei **config.json** und trage deine vier
   Zugangsdaten zwischen die Anführungszeichen ein (Server und Schulname
   findest du wie unten unter „Server und Schule herausfinden" beschrieben).
2. Öffne das Terminal in VS Code (Menü: **Terminal → New Terminal**) und führe aus:

   ```
   python3 main.py
   ```

3. Bei Erfolg erscheint `N Termine nach calendar.ics geschrieben`.
   Die Datei `calendar.ics` per Doppelklick in Apple Kalender importieren.

Die `config.json` steht in `.gitignore` und wird dadurch niemals zu GitHub
hochgeladen — dein Passwort bleibt auf deinem Mac. (Siehe auch
`config.example.json` für das Format.)

## Einrichtung

### 1. Server und Schule herausfinden

Öffne im Browser **webuntis.com**, suche deine Schule und melde dich an.
Die Adressleiste zeigt danach etwa:

```
https://erato.webuntis.com/WebUntis/?school=MeineSchule#/basic/timetable
```

- `WEBUNTIS_SERVER` = `erato.webuntis.com`
- `WEBUNTIS_SCHOOL` = `MeineSchule`
- `WEBUNTIS_USER` / `WEBUNTIS_PASSWORD` = deine App-Zugangsdaten

### 2. Auf GitHub hochladen

Erstelle ein neues GitHub-Repository (Standard-Branch `main`) und pushe
diesen Ordner. Für den Repo-Namen etwas Neutrales wählen (z. B.
`calendar-sync`) — siehe Hinweis zur Privatsphäre unten.

### 3. Secrets anlegen

Im Repository: **Settings → Secrets and variables → Actions → New repository secret**.
Je eines anlegen für:

| Secret            | Wert                                   |
|-------------------|----------------------------------------|
| WEBUNTIS_SERVER   | z. B. `erato.webuntis.com`             |
| WEBUNTIS_SCHOOL   | Schulname wie beim Web-Login           |
| WEBUNTIS_USER     | dein Benutzername                      |
| WEBUNTIS_PASSWORD | dein Passwort                          |

### 4. Workflow starten

Im Repository: **Actions → Stundenplan-Update → Run workflow**.
Danach liegt `calendar.ics` im Repo und der Zeitplan läuft automatisch
weiter (alle 2 Stunden).

### 5. In Apple Kalender abonnieren

Abo-URL (Platzhalter ersetzen):

```
https://raw.githubusercontent.com/<GitHub-User>/<Repo>/main/calendar.ics
```

- **Mac:** Kalender.app → Ablage → Neues Kalenderabo → URL einfügen.
- **iPhone:** Einstellungen → Apps → Kalender → Kalenderkonten →
  Kalenderabo hinzufügen (oder auf dem Mac abonnieren, dann per iCloud
  synchronisieren).

## Einstellungen

| Variable           | Standard        | Bedeutung                                  |
|--------------------|-----------------|--------------------------------------------|
| `WEEKS_AHEAD`      | 8               | Wochen, die im Voraus geholt werden        |
| `CAL_NAME`         | `Stundenplan`   | Anzeigename des Kalenders                  |
| `OUTPUT`           | `calendar.ics`  | Ausgabedatei                               |
| Aktualisierungsintervall | alle 2 Std. | cron-Ausdruck im Workflow anpassen   |

## Hinweise

- **Vertretungen/Ausfälle:** ausgefallene Stunden erscheinen als
  `[Ausfall] …` und werden im Mac-Kalender durchgestrichen angezeigt.
- **Zeitzone:** WebUntis liefert lokale Schulzeiten; die .ics nutzt
  "floating" Zeiten, dein Kalender interpretiert sie in deiner Zeitzone.
- **Privatsphäre:** `calendar.ics` enthält deinen persönlichen Stundenplan
  und liegt in einem öffentlichen Repo unter einer schwer zu ratenden,
  aber nicht geheimen URL. Wer die URL kennt, kann den Plan mitlesen.
  Repo-Name also neutral halten und die URL nicht teilen. Wer das
  ausschließen will, braucht stattdessen einen eigenen Server (z. B.
  Raspberry Pi), der die Datei ausliefert.
- **App vs. API:** die Untis-App nutzt teilweise andere Endpunkte; falls
  der Login hier fehlschlägt, obwohl die App funktioniert, kann die Schule
  den API-Zugriff eingeschränkt haben — dann hilft nur eine Nachfrage bei
  der Schul-IT.

## Erweiterungsideen

- Prüfungen (`lstype` / `code`) im Titel kennzeichnen
- Fächer nach eigenem Schema umbenennen
- Erinnerungen (Alarm) vor Stundenanfang setzen

## Dateien

```
├── main.py                          # Holt Stundenplan, erzeugt .ics
├── config.json                      # Deine Zugangsdaten (lokal, wird ignoriert von git)
├── config.example.json              # Beispielformat der Konfiguration
├── .github/workflows/update-calendar.yml  # Läuft alle 2 Stunden, committet die Datei
├── .gitignore
└── README.md
```
