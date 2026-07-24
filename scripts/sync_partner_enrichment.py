#!/usr/bin/env python3
"""Sync source-backed partner enrichment records into BottleCRM leads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from import_partner_research import (
    ApiError,
    BottleCrmClient,
    DEFAULT_BASE_URL,
    DEFAULT_ENV_FILE,
    TOKEN_NAME,
    load_env_value,
)


DEFAULT_EVIDENCE = Path(__file__).resolve().parents[1] / "research" / "partner_enrichment.json"
BEGIN_MARKER = "=== Aanvullend partneronderzoek ==="
END_MARKER = "=== Einde aanvullend partneronderzoek ==="
CORE_FIELD_MAPPING = (
    ("phone", "phone"),
    ("email", "email"),
    ("address_line", "address_line"),
    ("city", "city"),
    ("website", "website"),
)
REPLACEABLE_CORE_FIELDS = {crm_key for _, crm_key in CORE_FIELD_MAPPING}

CUSTOM_FIELDS = [
    {"key": "partner_enrichment_status", "label": "Enrichment status", "field_type": "dropdown", "options": [{"value": "Basis", "label": "Basis"}, {"value": "Uitgebreid", "label": "Uitgebreid"}, {"value": "Handmatig controleren", "label": "Handmatig controleren"}], "is_filterable": True},
    {"key": "partner_enrichment_date", "label": "Last enrichment date", "field_type": "date", "is_filterable": True},
    {"key": "partner_kvk", "label": "KvK number", "field_type": "text", "is_filterable": True},
    {"key": "partner_legal_form", "label": "Legal form", "field_type": "text", "is_filterable": True},
    {"key": "partner_employee_count", "label": "Employee count indication", "field_type": "number", "is_filterable": True},
    {"key": "partner_contact_person", "label": "Owner/contact person", "field_type": "text", "is_filterable": True},
    {"key": "partner_opening_hours", "label": "Opening hours", "field_type": "textarea", "is_filterable": False},
    {"key": "partner_work_area", "label": "Work area", "field_type": "text", "is_filterable": True},
    {"key": "partner_certifications", "label": "Certification evidence", "field_type": "textarea", "is_filterable": False},
    {"key": "partner_review_score_current", "label": "Current review score (out of 5)", "field_type": "number", "is_filterable": True},
    {"key": "partner_review_count_current", "label": "Current review count", "field_type": "number", "is_filterable": True},
    {"key": "partner_years_in_business", "label": "Years in business", "field_type": "number", "is_filterable": True},
]


def ensure_custom_fields(client: BottleCrmClient) -> int:
    definitions = client.get("/api/custom-fields/?target_model=Lead").get("definitions", [])
    existing = {item["key"]: item for item in definitions}
    created = 0
    for order, definition in enumerate(CUSTOM_FIELDS, start=200):
        current = existing.get(definition["key"])
        if current:
            if current["field_type"] != definition["field_type"]:
                raise RuntimeError(
                    f"Custom field {definition['key']} has type {current['field_type']}, "
                    f"expected {definition['field_type']}"
                )
            continue
        client.post(
            "/api/custom-fields/",
            {
                "target_model": "Lead",
                "is_required": False,
                "display_order": order,
                "is_active": True,
                **definition,
            },
        )
        created += 1
    return created


def get_research_leads(client: BottleCrmClient) -> dict[str, dict[str, Any]]:
    data = client.get("/api/leads/?limit=1000")
    leads = data["open_leads"]["open_leads"] + data["close_leads"]["close_leads"]
    return {
        lead["custom_fields"]["partner_research_id"]: lead
        for lead in leads
        if lead.get("custom_fields", {}).get("partner_research_id")
    }


def render_enrichment(entry: dict[str, Any]) -> str:
    facts = entry["facts"]
    labels = [
        ("kvk", "KvK"),
        ("legal_form", "Rechtsvorm"),
        ("contact_person", "Eigenaar/contactpersoon"),
        ("employee_count", "Medewerkersindicatie"),
        ("years_in_business", "Jaren actief"),
        ("phone", "Aanvullend telefoonnummer"),
        ("email", "Aanvullend e-mailadres"),
        ("address_line", "Aanvullend adres"),
        ("opening_hours", "Openingstijden"),
        ("work_area", "Werkgebied"),
        ("review_score_5", "Actuele reviewscore / 5"),
        ("review_count", "Actueel reviewaantal"),
        ("services", "Aanvullende diensten"),
        ("certifications", "Certificeringsbewijs"),
        ("notes", "Onderzoeksnotities/conflicten"),
    ]
    lines = [BEGIN_MARKER, f"Onderzocht op: {entry['researched_at']}"]
    lines.extend(f"- {label}: {facts[key]}" for key, label in labels if facts.get(key) not in (None, ""))
    lines.append("- Bronnen:")
    lines.extend(
        f"  - [{source['kind']}] {source['title']}: {source['url']}"
        for source in entry["sources"]
    )
    lines.append(END_MARKER)
    return "\n".join(lines)


def merge_description(original: str | None, rendered: str) -> str:
    description = original or ""
    if BEGIN_MARKER in description and END_MARKER in description:
        before, remainder = description.split(BEGIN_MARKER, 1)
        _, after = remainder.split(END_MARKER, 1)
        return f"{before.rstrip()}\n\n{rendered}{after}".strip()
    return f"{description.rstrip()}\n\n{rendered}".strip()


def enrichment_zzp_assessment(entry: dict[str, Any]) -> tuple[str, str]:
    """Prefer researched structure over the import's first-pass ZZP guess."""
    facts = entry["facts"]
    explicit = facts.get("zzp_likelihood")
    if explicit:
        if explicit not in {"Hoog", "Middel", "Laag", "Onbekend"}:
            raise RuntimeError(
                f"Invalid zzp_likelihood for {entry['record_id']}: {explicit}"
            )
        return explicit, facts.get(
            "zzp_basis", "Handmatig beoordeeld in aanvullend partneronderzoek"
        )

    employee_count = facts.get("employee_count")
    if isinstance(employee_count, (int, float)):
        if employee_count == 1:
            return "Hoog", "Aanvullend onderzoek bevestigt een eenpersoonsbedrijf"
        if employee_count >= 2:
            return (
                "Laag",
                f"Aanvullend onderzoek toont een team van circa {employee_count:g} personen",
            )

    legal_form = str(facts.get("legal_form", "")).lower()
    if "eenmanszaak" in legal_form or "sole proprietorship" in legal_form:
        return "Hoog", "Aanvullend onderzoek bevestigt een eenmanszaak"

    notes = str(facts.get("notes", "")).lower()
    negative_signals = (
        "not a freelancer",
        "not a zzp",
        "not a likely individual zzp",
        "not a classic individual zzp",
        "clearly not a zzp",
        "less likely to be a solo freelancer",
        "not a straightforward zzp",
        "rather than a freelancer",
    )
    if any(signal in notes for signal in negative_signals):
        return "Laag", "Aanvullend onderzoek wijst op een team of regulier bedrijf"

    positive_signals = (
        "clearest zzp",
        "strong zzp",
        "plausible zzp",
        "possible zzp",
        "could fit zzp",
        "genuine local one-person",
        "current one-person",
        "one-person profile",
        "strong freelancer signals",
    )
    if any(signal in notes for signal in positive_signals):
        return "Hoog", "Aanvullend onderzoek toont sterke eigenaar- of eenpersoonssignalen"

    return "Onbekend", "Aanvullend onderzoek bevestigt rechtsvorm of teamomvang nog niet"


def enrichment_custom_fields(entry: dict[str, Any]) -> dict[str, Any]:
    facts = entry["facts"]
    mapping = {
        "kvk": "partner_kvk",
        "legal_form": "partner_legal_form",
        "employee_count": "partner_employee_count",
        "contact_person": "partner_contact_person",
        "opening_hours": "partner_opening_hours",
        "work_area": "partner_work_area",
        "certifications": "partner_certifications",
        "review_score_5": "partner_review_score_current",
        "review_count": "partner_review_count_current",
        "years_in_business": "partner_years_in_business",
    }
    zzp_likelihood, zzp_basis = enrichment_zzp_assessment(entry)
    result = {
        "partner_enrichment_status": entry["status"],
        "partner_enrichment_date": entry["researched_at"],
        "partner_zzp_likelihood": zzp_likelihood,
        "partner_zzp_basis": zzp_basis,
    }
    result.update(
        {target: facts[source] for source, target in mapping.items() if facts.get(source) not in (None, "")}
    )
    return result


def build_patch(lead: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    facts = entry["facts"]
    payload: dict[str, Any] = {
        "description": merge_description(lead.get("description"), render_enrichment(entry)),
        "custom_fields": {
            **(lead.get("custom_fields") or {}),
            **enrichment_custom_fields(entry),
        },
    }
    # Fill missing core CRM fields. Existing values are only replaced when an
    # evidence record explicitly declares a source-backed correction.
    replace_core_fields = set(entry.get("replace_core_fields", []))
    unsupported = replace_core_fields - REPLACEABLE_CORE_FIELDS
    if unsupported:
        raise RuntimeError(
            f"Unsupported replace_core_fields for {entry['record_id']}: {sorted(unsupported)}"
        )
    for evidence_key, crm_key in CORE_FIELD_MAPPING:
        if facts.get(evidence_key) and (
            not lead.get(crm_key) or crm_key in replace_core_fields
        ):
            payload[crm_key] = facts[evidence_key]
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--commit", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = json.loads(args.evidence.read_text(encoding="utf-8"))
    ids = [entry["record_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate record_id in enrichment evidence")
    for entry in entries:
        if not entry.get("sources") or not entry.get("researched_at") or not entry.get("facts"):
            raise RuntimeError(f"Incomplete evidence record: {entry.get('record_id')}")

    client = BottleCrmClient(args.base_url, load_env_value(args.env_file, TOKEN_NAME))
    leads = get_research_leads(client)
    missing = [record_id for record_id in ids if record_id not in leads]
    if missing:
        raise RuntimeError(f"CRM leads not found for: {missing}")
    print(f"Evidence records: {len(entries)}; matching CRM leads: {len(ids)}")
    if not args.commit:
        print("Dry run only; pass --commit to create enrichment fields and update leads.")
        return 0

    created_fields = ensure_custom_fields(client)
    print(f"Custom fields created: {created_fields}")
    for entry in entries:
        lead = leads[entry["record_id"]]
        client.patch(f"/api/leads/{lead['id']}/", build_patch(lead, entry))
        print(f"Updated {entry['record_id']}: {lead.get('company_name')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
