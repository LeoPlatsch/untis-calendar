#!/usr/bin/env python3
"""Exportiert den persönlichen WebUntis-Stundenplan als .ics-Datei.

Einstellungen stehen in der Datei config.json (siehe config.example.json)
oder in Umgebungsvariablen (GitHub Secrets). Umgebungsvariablen haben
Vorrang vor config.json. Wichtig:

  WEBUNTIS_SERVER     Server deiner Schule, z. B. "erato.webuntis.com"
  WEBUNTIS_SCHOOL     Schulname wie beim WebUntis-Login
  WEBUNTIS_USER       Benutzername (wie in der Untis-App)
  WEBUNTIS_PASSWORD   Passwort
  WEEKS_AHEAD         optional: Wochen im Voraus (Standard 8)
  CAL_NAME            optional: Kalendername (Standard "Stundenplan")
  OUTPUT              optional: Ausgabedatei (Standard "calendar.ics")
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

API_PATH = "/WebUntis/jsonrpc.do"
CLIENT_NAME = "untis-calendar-sync"
CONFIG_FILE = "config.json"

# Stundenplan-Feld -> API-Methode für die Stammdaten
FIELD_METHODS = {
    "su": "getSubjects",  # Fächer
    "te": "getTeachers",  # Lehrkräfte
    "ro": "getRooms",     # Räume
}


class WebUntisError(Exception):
    pass


class WebUntis:
    """Minimaler Client für die JSON-RPC-Schnittstelle von WebUntis."""

    def __init__(self, server, school):
        self.url = "https://{}{}?school={}".format(
            server, API_PATH, urllib.parse.quote(school))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor())

    def call(self, method, params=None):
        body = json.dumps({
            "id": CLIENT_NAME,
            "method": method,
            "params": params if params is not None else {},
            "jsonrpc": "2.0",
        }).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body,
            headers={"Content-Type": "application/json; charset=utf-8"})
        with self.opener.open(request, timeout=30) as response:
            reply = json.loads(response.read().decode("utf-8"))
        if "error" in reply:
            raise WebUntisError("{} fehlgeschlagen: {}".format(
                method, reply["error"].get("message", reply["error"])))
        return reply["result"]

    def login(self, user, password):
        return self.call("authenticate", {
            "user": user,
            "password": password,
            "client": CLIENT_NAME,
        })

    def logout(self):
        self.call("logout")


def as_list(result):
    """WebUntis liefert Listen je nach Version direkt oder eingepackt."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("data", "timetable"):
            value = result.get(key)
            if isinstance(value, list):
                return value
    return []


def fetch_master_data(untis):
    """Lädt Fächer, Lehrkräfte und Räume, um IDs in Namen aufzulösen."""
    master = {}
    for field, method in FIELD_METHODS.items():
        try:
            items = as_list(untis.call(method))
            master[field] = {item["id"]: item for item in items}
        except (WebUntisError, KeyError):
            master[field] = {}
    return master


def lookup(period, field, master, prefer_long):
    """Löst die IDs in einem Stunden-Feld zu Anzeigenamen auf."""
    names = []
    for ref in period.get(field) or []:
        entry = master.get(field, {}).get(ref.get("id"))
        if not entry:
            continue
        if prefer_long:
            names.append(entry.get("longname") or entry.get("name") or "")
        else:
            names.append(entry.get("name") or entry.get("longname") or "")
    return [name for name in names if name]


def esc(text):
    """Maskiert Sonderzeichen gemäß iCalendar (RFC 5545)."""
    text = str(text)
    return (text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n"))


def fold(line):
    """Bricht Zeilen über 75 Zeichen RFC-konform um."""
    if len(line) <= 75:
        return [line]
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return parts


def format_time(value):
    """800 -> "080000" (WebUntis liefert HHMM als Zahl)."""
    digits = "{:04d}".format(int(value))
    return digits[:2] + digits[2:] + "00"


def event_lines(period, master, stamp):
    subjects = lookup(period, "su", master, prefer_long=False)
    long_subjects = lookup(period, "su", master, prefer_long=True)
    teachers = lookup(period, "te", master, prefer_long=True)
    rooms = lookup(period, "ro", master, prefer_long=False)

    cancelled = period.get("code") == "CANCELLED"
    info = (period.get("info") or "").strip()
    subst = (period.get("substText") or "").strip()

    summary = ", ".join(subjects) or info or "Unterricht"
    if cancelled:
        summary = "[Ausfall] " + summary

    description = []
    if long_subjects and long_subjects != subjects:
        description.append(", ".join(long_subjects))
    if teachers:
        description.append("Lehrkraft: " + ", ".join(teachers))
    description.extend(text for text in (info, subst) if text)

    date_str = str(period["date"])
    lines = [
        "BEGIN:VEVENT",
        "UID:untis-{}-{}@webuntis".format(period.get("id", 0), date_str),
        "DTSTAMP:" + stamp,
        "DTSTART:{}T{}".format(date_str, format_time(period["startTime"])),
        "DTEND:{}T{}".format(date_str, format_time(period["endTime"])),
        "SUMMARY:" + esc(summary),
    ]
    if rooms:
        lines.append("LOCATION:" + esc(", ".join(rooms)))
    if description:
        lines.append("DESCRIPTION:" + esc("\n".join(description)))
    if cancelled:
        lines.append("STATUS:CANCELLED")
    lines.append("END:VEVENT")
    return lines


def build_ics(periods, master, cal_name):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//untis-calendar-sync//Stundenplan//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + esc(cal_name),
    ]
    count = 0
    for period in sorted(
            periods,
            key=lambda p: (p.get("date", 0), p.get("startTime", 0))):
        # Einträge ohne Fach, Info oder Lehrkraft überspringen (z. B. Pausen)
        if not (period.get("su") or period.get("info") or period.get("te")):
            continue
        for line in event_lines(period, master, stamp):
            lines.extend(fold(line))
        count += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", count


def clean_server(server):
    """Nimmt Schema und Pfad aus der Server-Angabe ("https://x.com/WebUntis/" -> "x.com")."""
    server = server.strip()
    for prefix in ("https://", "http://"):
        if server.startswith(prefix):
            server = server[len(prefix):]
    return server.split("/")[0]


def load_config():
    """Liest config.json; fehlt sie oder ist sie ungültig, ist das Ergebnis leer."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def main():
    config = load_config()
    required = ("WEBUNTIS_SERVER", "WEBUNTIS_SCHOOL",
                "WEBUNTIS_USER", "WEBUNTIS_PASSWORD")
    for name in required:
        env_value = os.environ.get(name, "")
        if env_value:
            config[name] = env_value
        config[name] = str(config.get(name, "")).strip()
    missing = [name for name in required if not config[name]]
    if missing:
        sys.exit("Fehlende Angaben (config.json oder Umgebungsvariablen): "
                 + ", ".join(missing))
    config["WEBUNTIS_SERVER"] = clean_server(config["WEBUNTIS_SERVER"])

    weeks = int(config.get("WEEKS_AHEAD", 8))
    cal_name = str(config.get("CAL_NAME", "Stundenplan"))
    output = str(config.get("OUTPUT", "calendar.ics"))

    start = date.today()
    end = start + timedelta(days=weeks * 7)

    untis = WebUntis(config["WEBUNTIS_SERVER"], config["WEBUNTIS_SCHOOL"])
    auth = untis.login(config["WEBUNTIS_USER"], config["WEBUNTIS_PASSWORD"])
    try:
        periods = as_list(untis.call("getTimetable", {
            "id": auth["personId"],
            "type": auth["personType"],
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }))
        master = fetch_master_data(untis)
    finally:
        try:
            untis.logout()
        except WebUntisError:
            pass

    ics, count = build_ics(periods, master, cal_name)
    with open(output, "w", encoding="utf-8", newline="") as handle:
        handle.write(ics)
    print("{} Termine nach {} geschrieben".format(count, output))


if __name__ == "__main__":
    main()
