"""Safe, deliberately small template renderer for lead email."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

PLACEHOLDER_RE = re.compile(r"{{\s*([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)\s*}}")
ALLOWED_VARIABLES = {
    "lead.first_name": "Voornaam van de lead",
    "lead.last_name": "Achternaam van de lead",
    "lead.full_name": "Volledige naam van de lead",
    "lead.company_name": "Bedrijfsnaam van de lead",
    "lead.email": "E-mailadres van de lead",
    "lead.city": "Plaats van de lead",
    "lead.postcode": "Postcode van de lead",
    "organization.name": "Naam van de organisatie",
    "sender.name": "Naam van de afzender",
    "sender.email": "E-mailadres van de afzender",
}
CUSTOM_PREFIX = "lead.custom."


@dataclass(frozen=True)
class RenderResult:
    subject: str
    body_text: str
    body_html: str
    missing_variables: list[str]
    unknown_variables: list[str]

    @property
    def valid(self) -> bool:
        return not self.missing_variables and not self.unknown_variables


def text_to_html(value: str) -> str:
    """Create a safe HTML alternative from plain text."""
    paragraphs = [
        f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>"
        for part in value.split("\n\n")
    ]
    return "".join(paragraphs)


def find_variables(*values: str) -> set[str]:
    variables: set[str] = set()
    for value in values:
        variables.update(PLACEHOLDER_RE.findall(value or ""))
    return variables


def find_unknown_variables(*values: str) -> list[str]:
    return sorted(
        variable
        for variable in find_variables(*values)
        if variable not in ALLOWED_VARIABLES and not variable.startswith(CUSTOM_PREFIX)
    )


def _context(*, lead, organization, sender) -> dict[str, str]:
    first_name = (lead.first_name or "").strip()
    last_name = (lead.last_name or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    sender_user = getattr(sender, "user", None)
    sender_email = getattr(sender_user, "email", "") or ""
    sender_name = getattr(sender_user, "name", "") or sender_email
    values = {
        "lead.first_name": first_name,
        "lead.last_name": last_name,
        "lead.full_name": full_name,
        "lead.company_name": (lead.company_name or "").strip(),
        "lead.email": (lead.email or "").strip(),
        "lead.city": (lead.city or "").strip(),
        "lead.postcode": (lead.postcode or "").strip(),
        "organization.name": (
            organization.company_name or organization.name or ""
        ).strip(),
        "sender.name": sender_name.strip(),
        "sender.email": sender_email.strip(),
    }
    for key, value in (lead.custom_fields or {}).items():
        values[f"{CUSTOM_PREFIX}{key}"] = "" if value is None else str(value).strip()
    return values


def render_email(*, subject: str, body_text: str, lead, organization, sender):
    values = _context(lead=lead, organization=organization, sender=sender)
    variables = find_variables(subject, body_text)
    unknown = find_unknown_variables(subject, body_text)
    missing = sorted(
        variable
        for variable in variables
        if variable not in unknown and not values.get(variable, "")
    )

    def replace(match):
        variable = match.group(1)
        return values.get(variable, match.group(0))

    rendered_subject = PLACEHOLDER_RE.sub(replace, subject)
    rendered_body = PLACEHOLDER_RE.sub(replace, body_text)
    return RenderResult(
        subject=rendered_subject,
        body_text=rendered_body,
        body_html=text_to_html(rendered_body),
        missing_variables=missing,
        unknown_variables=unknown,
    )
