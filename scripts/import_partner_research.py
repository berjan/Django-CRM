#!/usr/bin/env python3
"""Import the Bruens partner-research master CSV into BottleCRM leads.

The importer uses only the public REST API. It is dry-run by default and is
idempotent once committed: ``partner_research_id`` is used as the stable key.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path(__file__).resolve().parents[1] / "research" / (
    "partneronderzoek_zzp_installateurs_uitgebreid_v4.csv"
)
DEFAULT_ENV_FILE = Path.home() / ".env.local"
DEFAULT_BASE_URL = "http://127.0.0.1:18080"
TOKEN_NAME = "BRUENS_DT_CRM_API_KEY"


CUSTOM_FIELDS = [
    {
        "key": "partner_research_id",
        "label": "Partner research ID",
        "field_type": "text",
        "is_filterable": True,
    },
    {
        "key": "partner_priority",
        "label": "Partner priority",
        "field_type": "dropdown",
        "options": [
            {"value": value, "label": value}
            for value in ("A", "B", "C", "PARTNER", "UNKNOWN")
        ],
        "is_filterable": True,
    },
    {
        "key": "partner_rank",
        "label": "Partner rank",
        "field_type": "number",
        "is_filterable": True,
    },
    {
        "key": "partner_role",
        "label": "Partner role",
        "field_type": "text",
        "is_filterable": True,
    },
    {
        "key": "partner_data_quality",
        "label": "Partner data quality",
        "field_type": "dropdown",
        "options": [
            {"value": value, "label": value}
            for value in ("Hoog", "Middel", "Laag", "Onbekend")
        ],
        "is_filterable": True,
    },
    {
        "key": "partner_cert_evidence",
        "label": "Partner certification evidence",
        "field_type": "dropdown",
        "options": [
            {"value": value, "label": value}
            for value in ("Hoog", "Middel", "Laag", "Onbekend")
        ],
        "is_filterable": True,
    },
    {
        "key": "partner_distance",
        "label": "Partner distance",
        "field_type": "text",
        "is_filterable": True,
    },
    {
        "key": "partner_contact_status",
        "label": "Partner contact status",
        "field_type": "text",
        "is_filterable": True,
    },
    {
        "key": "partner_platform",
        "label": "Partner platform",
        "field_type": "text",
        "is_filterable": True,
    },
    {
        "key": "partner_review_score",
        "label": "Partner review score (out of 5)",
        "field_type": "number",
        "is_filterable": True,
    },
    {
        "key": "partner_review_count",
        "label": "Partner review count",
        "field_type": "number",
        "is_filterable": True,
    },
    {
        "key": "partner_research_date",
        "label": "Partner research date",
        "field_type": "date",
        "is_filterable": True,
    },
    {
        "key": "partner_new_round",
        "label": "Added in new research round",
        "field_type": "checkbox",
        "is_filterable": True,
    },
    {
        "key": "partner_zzp_likelihood",
        "label": "ZZP likelihood",
        "field_type": "dropdown",
        "options": [
            {"value": value, "label": value}
            for value in ("Hoog", "Middel", "Laag", "Onbekend")
        ],
        "is_filterable": True,
    },
    {
        "key": "partner_zzp_basis",
        "label": "ZZP likelihood basis",
        "field_type": "text",
        "is_filterable": False,
    },
]


class ApiError(RuntimeError):
    pass


class BottleCrmClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=body, headers=self.headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc)
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = exc.reason
            raise ApiError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path} failed: {exc.reason}") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict) -> Any:
        return self.request("POST", path, payload)

    def patch(self, path: str, payload: dict) -> Any:
        return self.request("PATCH", path, payload)


def load_env_value(path: Path, name: str) -> str:
    """Read one dotenv value without sourcing the file or changing PATH."""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line.startswith(f"{name}="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            return value
    raise RuntimeError(f"{name} is missing from {path}")


def priority_parts(raw: str) -> tuple[str, int | None]:
    value = (raw or "").strip().upper()
    match = re.fullmatch(r"([ABC])(\d+)?", value)
    if match:
        return match.group(1), int(match.group(2)) if match.group(2) else None
    if value == "PARTNER":
        return value, None
    return "UNKNOWN", None


def evidence_level(raw: str) -> str:
    value = (raw or "").strip()
    for level in ("Hoog", "Middel", "Laag", "Onbekend"):
        if value.startswith(level):
            return level
    return "Onbekend"


def zzp_likelihood(row: dict[str, str]) -> tuple[str, str]:
    """Classify explicit platform evidence first, then conservative size signals."""
    explicit = (row.get("zzp_of_kleinbedrijf_indicatie") or "").strip()
    if explicit:
        if explicit.startswith("Hoog"):
            return "Hoog", f"Expliciet platformonderzoek: {explicit}"
        if explicit.startswith("Middel"):
            return "Middel", f"Expliciet platformonderzoek: {explicit}"
        return "Laag", f"Expliciet platformonderzoek: {explicit}"

    organisation = " | ".join(
        [row.get("rechtsvorm_en_omvang", ""), row.get("type_bedrijf", "")]
    ).lower()
    high_signals = (
        "eenmanszaak",
        "zelfstandige",
        "1 werkzaam persoon",
        "1 medewerker",
        "eigenaar/monteur",
        "zzp",
    )
    low_signals = (
        "groot technisch",
        "grote/brede",
        "middelgroot",
        "grotere installatie",
        "landelijke franchise",
        "grote organisatie",
    )
    if any(signal in organisation for signal in high_signals):
        return "Hoog", "Afgeleid uit eenmanszaak-, zelfstandige- of eenpersoonssignaal"
    if any(signal in organisation for signal in low_signals):
        return "Laag", "Afgeleid uit middelgrote/grote organisatiesignalen"
    if "klein" in organisation or "kleine" in organisation:
        return "Middel", "Afgeleid uit kleinbedrijfsignaal; ZZP-status niet bevestigd"
    return "Onbekend", "Onvoldoende openbaar signaal over rechtsvorm of omvang"


def review_score(raw: str) -> float | None:
    value = (raw or "").strip().replace(",", ".")
    if not value:
        return None
    if value.endswith("/10"):
        return round(float(value[:-3]) / 2, 2)
    return float(value)


def positive_int(raw: str) -> int | None:
    try:
        return int((raw or "").strip())
    except ValueError:
        return None


def research_date(raw: str) -> str | None:
    """Return the latest ISO date when a merged row contains multiple dates."""
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", raw or "")
    return max(dates) if dates else None


def usable_phone(raw: str) -> str | None:
    """Select the first valid CRM-sized number; preserve the original in notes."""
    first = re.split(r"\s*/\s*", (raw or "").strip(), maxsplit=1)[0]
    return first if 7 <= len(first) <= 25 and re.fullmatch(r"[\d\s\-()+.]+", first) else None


def usable_email(raw: str) -> str | None:
    value = (raw or "").strip()
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) else None


def usable_url(raw: str) -> str | None:
    value = (raw or "").strip()
    return value if value.startswith(("https://", "http://")) else None


def note_section(title: str, rows: list[tuple[str, str]]) -> str:
    populated = [(label, value.strip()) for label, value in rows if (value or "").strip()]
    if not populated:
        return ""
    return title + "\n" + "\n".join(f"- {label}: {value}" for label, value in populated)


def build_description(row: dict[str, str]) -> str:
    capabilities = [
        ("Airco", row["airco_installatie"]),
        ("F-gas/inbedrijfstelling", row["fgas_of_inbedrijfstelling"]),
        ("Elektrotechniek", row["elektrotechniek"]),
        ("Meterkast/groepenkast", row["meterkast_of_groepenkast"]),
        ("Zonnepanelen/PV", row["zonnepanelen_of_pv"]),
        ("Thuisbatterij/EMS", row["thuisbatterij_of_ems"]),
        ("Laadpalen", row["laadpalen"]),
        ("Warmtepompen", row["warmtepompen"]),
        ("Service/onderhoud/storingen", row["service_onderhoud_storingen"]),
    ]
    sections = [
        note_section(
            "Onderzoeksprofiel",
            [
                ("Research-ID", row["record_id"]),
                ("Onderzoeksronde", row["onderzoeksrondes"]),
                ("Primaire partnerrol", row["primaire_partnerrol"]),
                ("Secundaire partnerrollen", row["secundaire_partnerrollen"]),
                ("Prioriteit", row["prioriteit"]),
                ("Datakwaliteit", row["datakwaliteit"]),
                ("Bereikbaarheid", row["bereikbaarheid"]),
                ("Afstand", row["afstand_tot_apeldoorn"]),
                ("Afstandscategorie", row.get("afstandscategorie", "")),
                ("Bedrijfstype", row["type_bedrijf"]),
                ("Rechtsvorm/omvang", row["rechtsvorm_en_omvang"]),
                ("Verwachte flexibiliteit", row["waarschijnlijke_flexibiliteit"]),
                ("Commerciële oriëntatie", row["waarschijnlijke_commerciele_orientatie"]),
            ],
        ),
        note_section(
            "Contact",
            [
                ("Origineel telefoonveld", row["telefoon"]),
                ("Origineel e-mailveld", row["email"]),
                ("Contactroute", row["contactroute"]),
                ("Aanbevolen kanaal", row.get("benaderkanaal_aanbevolen", "")),
                ("Contactstatus", row["contactstatus"]),
            ],
        ),
        note_section(
            "Ervaring en inzetbaarheid",
            [
                ("Activiteiten en ervaring", row["activiteiten_en_ervaring"]),
                ("Ideale klustypen", row["ideale_klustypen"]),
                *capabilities,
            ],
        ),
        note_section(
            "Certificering",
            [
                ("Geclaimd", row["certificering_geclaimd"]),
                ("BRL100/CRT", row["brl100_of_crt_status"]),
                ("Persoonlijk F-gas", row["persoonlijk_fgas_status"]),
                ("Bewijskracht", row["certificeringsbewijskracht"]),
                ("Nog controleren", row["certificaten_en_bewijs_nog_controleren"]),
            ],
        ),
        note_section(
            "Benadering en kwalificatie",
            [
                ("Waarom interessant", row["waarom_interessant_voor_bruins"]),
                ("Persoonlijke benaderhaak", row["persoonlijke_benaderhaak"]),
                ("Bezwaren/blokkades", row["mogelijke_bezwaren_of_blokkades"]),
                ("Risico's/aandachtspunten", row["risicos_en_aandachtspunten"]),
                ("Review-risicosignaal", row.get("review_risicosignaal", "")),
                ("Aanbevolen pilot", row["aanbevolen_pilot"]),
                ("Eerste actie", row["aanbevolen_eerste_actie"]),
                ("Kwalificatiecheck", row["kwalificatiecheck"]),
            ],
        ),
        note_section(
            "Bronnen",
            [
                ("Bron 1", row["bron_url_1"]),
                ("Bron 2", row["bron_url_2"]),
                ("Platform", row.get("platform_hoofdbron", "")),
                ("Platformprofiel", row.get("platform_profiel_url", "")),
                ("Reviewscore", row.get("platform_reviewscore", "")),
                ("Aantal reviews", row.get("platform_aantal_reviews", "")),
                ("Onderzoeksdatum", row["onderzoeksdatum"]),
                ("Verificatieadvies", row["laatste_verificatie_advies"]),
            ],
        ),
    ]
    return "\n\n".join(section for section in sections if section)


def build_payload(row: dict[str, str]) -> dict[str, Any]:
    priority, rank = priority_parts(row["prioriteit"])
    zzp_value, zzp_basis = zzp_likelihood(row)
    score = review_score(row.get("platform_reviewscore", ""))
    count = positive_int(row.get("platform_aantal_reviews", ""))
    custom_fields: dict[str, Any] = {
        "partner_research_id": row["record_id"],
        "partner_priority": priority,
        "partner_role": row["primaire_partnerrol"],
        "partner_data_quality": row["datakwaliteit"] or "Onbekend",
        "partner_cert_evidence": evidence_level(row["certificeringsbewijskracht"]),
        "partner_distance": row.get("afstandscategorie") or row["afstand_tot_apeldoorn"],
        "partner_contact_status": row["contactstatus"],
        "partner_platform": row.get("platform_hoofdbron", ""),
        "partner_new_round": row.get("nieuwe_onderzoeksronde", "").startswith("Ja"),
        "partner_zzp_likelihood": zzp_value,
        "partner_zzp_basis": zzp_basis,
    }
    if rank is not None:
        custom_fields["partner_rank"] = rank
    if score is not None:
        custom_fields["partner_review_score"] = score
    if count is not None:
        custom_fields["partner_review_count"] = count
    researched_on = research_date(row["onderzoeksdatum"])
    if researched_on is not None:
        custom_fields["partner_research_date"] = researched_on

    rating = {"A": "HOT", "B": "WARM", "C": "COLD", "PARTNER": "HOT"}.get(
        priority, "WARM"
    )
    payload: dict[str, Any] = {
        "title": f"Uitvoeringspartner – {row['primaire_partnerrol']}",
        "company_name": row["bedrijfsnaam"],
        "status": "assigned",
        "source": "partner",
        "industry": "SERVICE",
        "rating": rating,
        "address_line": row["adres"] or None,
        "city": row["plaats"] or None,
        "country": "NL",
        "description": build_description(row),
        "is_active": True,
        "custom_fields": custom_fields,
    }
    phone = usable_phone(row["telefoon"])
    email = usable_email(row["email"])
    website = usable_url(row["website_of_profiel"])
    if phone:
        payload["phone"] = phone
    if email:
        payload["email"] = email
    if website:
        payload["website"] = website
    return {key: value for key, value in payload.items() if value is not None}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row.get("record_id", "") for row in rows]
    if not rows or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RuntimeError("CSV must contain non-empty, unique record_id values")
    return rows


def existing_research_leads(client: BottleCrmClient) -> dict[str, dict[str, Any]]:
    query = urllib.parse.urlencode({"limit": 1000})
    data = client.get(f"/api/leads/?{query}")
    leads = data["open_leads"]["open_leads"] + data["close_leads"]["close_leads"]
    return {
        lead["custom_fields"]["partner_research_id"]: lead
        for lead in leads
        if lead.get("custom_fields", {}).get("partner_research_id")
    }


def backfill_zzp_fields(
    client: BottleCrmClient,
    rows: list[dict[str, str]],
    existing: dict[str, dict[str, Any]],
) -> int:
    updated = 0
    for row in rows:
        lead = existing.get(row["record_id"])
        if not lead:
            continue
        likelihood, basis = zzp_likelihood(row)
        current = lead.get("custom_fields") or {}
        if (
            current.get("partner_zzp_likelihood") == likelihood
            and current.get("partner_zzp_basis") == basis
        ):
            continue
        client.patch(
            f"/api/leads/{lead['id']}/",
            {
                "custom_fields": {
                    **current,
                    "partner_zzp_likelihood": likelihood,
                    "partner_zzp_basis": basis,
                }
            },
        )
        updated += 1
    return updated


def ensure_custom_fields(client: BottleCrmClient) -> int:
    data = client.get("/api/custom-fields/?target_model=Lead")
    existing = {item["key"]: item for item in data.get("definitions", [])}
    created = 0
    for order, definition in enumerate(CUSTOM_FIELDS, start=100):
        current = existing.get(definition["key"])
        if current:
            if current["field_type"] != definition["field_type"]:
                raise RuntimeError(
                    f"Lead custom field {definition['key']} exists with type "
                    f"{current['field_type']}, expected {definition['field_type']}"
                )
            continue
        payload = {
            "target_model": "Lead",
            "is_required": False,
            "display_order": order,
            "is_active": True,
            **definition,
        }
        client.post("/api/custom-fields/", payload)
        created += 1
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--commit", action="store_true", help="Write to BottleCRM")
    parser.add_argument("--limit", type=int, help="Process only the first N rows")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_rows(args.csv)
    if args.limit is not None:
        rows = rows[: args.limit]
    token = load_env_value(args.env_file, TOKEN_NAME)
    client = BottleCrmClient(args.base_url, token)

    org = client.get("/api/org/settings/")
    print(f"Tenant: {org.get('name')} ({org.get('id')})")
    print(f"CSV: {args.csv} ({len(rows)} rows)")
    existing = existing_research_leads(client)
    pending = [row for row in rows if row["record_id"] not in existing]
    zzp_backfill = sum(
        1
        for row in rows
        if row["record_id"] in existing
        and (
            existing[row["record_id"]].get("custom_fields", {}).get(
                "partner_zzp_likelihood"
            )
            != zzp_likelihood(row)[0]
            or existing[row["record_id"]].get("custom_fields", {}).get(
                "partner_zzp_basis"
            )
            != zzp_likelihood(row)[1]
        )
    )
    print(f"Existing research leads: {len(existing)}")
    print(f"Pending: {len(pending)}; skipped as existing: {len(rows) - len(pending)}")
    print(f"ZZP fields needing backfill: {zzp_backfill}")

    if not args.commit:
        print("Dry run only; pass --commit to create custom fields and leads.")
        return 0

    created_fields = ensure_custom_fields(client)
    print(f"Custom fields created: {created_fields}")
    updated = backfill_zzp_fields(client, rows, existing)
    print(f"Existing leads backfilled with ZZP fields: {updated}")
    created = 0
    for row in pending:
        client.post("/api/leads/", build_payload(row))
        created += 1
        if created % 25 == 0 or created == len(pending):
            print(f"Created {created}/{len(pending)} leads")

    print(f"Import complete: {created} created, {len(rows) - len(pending)} skipped")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
