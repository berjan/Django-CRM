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


@dataclass(frozen=True)
class OutboundRenderResult:
    body_text: str
    body_html: str


def text_to_html(value: str) -> str:
    """Create a safe HTML alternative from plain text."""
    paragraphs = [
        f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>"
        for part in value.split("\n\n")
    ]
    return "".join(paragraphs)


def _link(value: str, label: str, color: str) -> str:
    return (
        f'<a href="{html.escape(value, quote=True)}" '
        f'style="color:{color};text-decoration:none;">'
        f"{html.escape(label)}</a>"
    )


def _signature_html(signature) -> str:
    primary = (
        signature.primary_color
        if re.fullmatch(r"#[0-9a-fA-F]{6}", signature.primary_color)
        else "#426451"
    )
    accent = (
        signature.accent_color
        if re.fullmatch(r"#[0-9a-fA-F]{6}", signature.accent_color)
        else "#F28C00"
    )
    sender_name = html.escape(signature.sender_name)
    sender_role = html.escape(signature.sender_role)
    company_name = html.escape(signature.company_name)
    address = html.escape(signature.address)

    contact_lines = []
    if signature.phone_number:
        phone_href = re.sub(r"[^+0-9]", "", signature.phone_number)
        contact_lines.append(
            _link(f"tel:{phone_href}", signature.phone_number, primary)
        )
    if signature.email_address:
        contact_lines.append(
            _link(
                f"mailto:{signature.email_address}",
                signature.email_address,
                primary,
            )
        )
    if signature.website_url:
        website_label = re.sub(r"^https?://", "", signature.website_url).rstrip("/")
        contact_lines.append(_link(signature.website_url, website_label, primary))
    contact_html = "<br>".join(contact_lines)

    logo_html = ""
    if signature.logo_url:
        logo_html = (
            f'<img src="{html.escape(signature.logo_url, quote=True)}" '
            f'alt="{company_name}" width="300" '
            'style="display:block;width:100%;max-width:300px;height:auto;border:0;">'
        )

    certification_cells = []
    for certification in signature.certifications:
        name = html.escape(str(certification.get("name", "")))
        image_url = html.escape(str(certification.get("image_url", "")), quote=True)
        target_url = html.escape(str(certification.get("url", "")), quote=True)
        if not name:
            continue
        image = ""
        if image_url:
            image = (
                f'<img src="{image_url}" alt="{name}" height="38" '
                'style="display:block;height:38px;width:auto;max-width:84px;'
                'margin:0 auto 6px;border:0;object-fit:contain;">'
            )
        content = (
            f'{image}<span style="color:#4b5563;font-size:11px;line-height:15px;">'
            f"{name}</span>"
        )
        if target_url:
            content = (
                f'<a href="{target_url}" style="text-decoration:none;">{content}</a>'
            )
        certification_cells.append(
            '<td valign="top" align="center" width="33%" '
            'style="padding:8px 6px;background:#f7f8f7;border-right:4px solid #ffffff;">'
            f"{content}</td>"
        )

    certifications_html = ""
    if certification_cells:
        certifications_html = (
            '<tr><td colspan="2" style="padding-top:16px;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'width="100%"><tr>'
            f"{''.join(certification_cells)}</tr></table></td></tr>"
        )

    proof_html = ""
    if signature.review_score and signature.review_count and signature.reviews_url:
        score = str(signature.review_score).replace(".", ",")
        reviews_url = html.escape(signature.reviews_url, quote=True)
        projects_url = html.escape(signature.projects_url, quote=True)
        projects_link = ""
        if projects_url:
            projects_link = (
                '<span style="color:#cbd5cf;padding:0 7px;">|</span>'
                f'<a href="{projects_url}" style="color:{primary};font-size:12px;'
                'font-weight:bold;text-decoration:none;white-space:nowrap;">'
                "Bekijk onze projecten&nbsp;&rarr;</a>"
            )
        proof_html = (
            '<tr><td colspan="2" style="padding-top:8px;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'width="100%" style="border-collapse:collapse;background:#f7f8f7;">'
            '<tr><td valign="middle" style="padding:10px 12px;">'
            f'<span style="color:{accent};font-size:16px;letter-spacing:1px;'
            'white-space:nowrap;">&#9733;&#9733;&#9733;&#9733;&#9733;</span>'
            f'<span style="padding-left:8px;color:#243229;font-size:14px;'
            f'font-weight:bold;white-space:nowrap;">{score}/10</span>'
            f'<span style="padding-left:5px;color:#6b7280;font-size:11px;'
            f'white-space:nowrap;">uit {signature.review_count}+ beoordelingen</span>'
            '</td><td valign="middle" align="right" style="padding:10px 12px;">'
            f'<a href="{reviews_url}" style="color:{primary};font-size:12px;'
            'font-weight:bold;text-decoration:none;white-space:nowrap;">'
            f"Bekijk onze reviews&nbsp;&rarr;</a>{projects_link}</td></tr></table></td></tr>"
        )

    role_html = (
        f'<div style="font-size:13px;line-height:18px;color:#6b7280;">{sender_role}</div>'
        if sender_role
        else ""
    )
    address_html = (
        f'<div style="margin-top:5px;color:#6b7280;font-size:12px;line-height:17px;">'
        f"{address}</div>"
        if address
        else ""
    )
    return (
        '<div style="margin-top:28px;max-width:600px;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="margin-bottom:14px;font-size:14px;line-height:20px;color:#243229;">'
        "Met vriendelijke groet,</div>"
        f'<div style="height:3px;background:{accent};font-size:0;line-height:0;">&nbsp;</div>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'width="100%" style="border-collapse:collapse;background:#ffffff;">'
        '<tr><td valign="top" style="padding:16px 18px 8px 0;">'
        f'<div style="font-size:18px;line-height:24px;font-weight:bold;color:{primary};">'
        f"{sender_name}</div>{role_html}"
        f'<div style="margin-top:8px;font-size:13px;line-height:18px;font-weight:bold;color:#243229;">'
        f"{company_name}</div>"
        f'<div style="margin-top:5px;font-size:13px;line-height:19px;">{contact_html}</div>'
        f"{address_html}</td>"
        '<td valign="top" align="right" style="padding:18px 0 8px 16px;">'
        f"{logo_html}</td></tr>{certifications_html}{proof_html}</table></div>"
    )


def render_outbound_email(
    body_text: str, *, organization, signature=None
) -> OutboundRenderResult:
    """Render the final text and branded HTML sent through every mail path."""
    if signature is None:
        from communications.models import EmailSignature

        signature = EmailSignature.objects.filter(
            org=organization, is_enabled=True
        ).first()
    if signature is None or not signature.is_enabled:
        return OutboundRenderResult(
            body_text=body_text, body_html=text_to_html(body_text)
        )

    content = body_text.rstrip()
    certification_names = [
        str(item.get("name", "")).strip()
        for item in signature.certifications
        if str(item.get("name", "")).strip()
    ]
    signature_lines = [
        "Met vriendelijke groet,",
        "",
        signature.sender_name,
    ]
    if signature.sender_role:
        signature_lines.append(signature.sender_role)
    signature_lines.append(signature.company_name)
    signature_lines.extend(
        value
        for value in (
            signature.phone_number,
            signature.email_address,
            signature.website_url,
            signature.address,
        )
        if value
    )
    if certification_names:
        signature_lines.extend(("", " | ".join(certification_names)))
    if signature.review_score and signature.review_count and signature.reviews_url:
        score = str(signature.review_score).replace(".", ",")
        signature_lines.extend(
            (
                "",
                f"Klantbeoordeling: {score}/10 uit {signature.review_count}+ beoordelingen",
                f"Reviews: {signature.reviews_url}",
            )
        )
    if signature.projects_url:
        signature_lines.append(f"Projecten: {signature.projects_url}")
    final_text = f"{content}\n\n" + "\n".join(signature_lines)
    final_html = (
        '<div style="max-width:600px;font-family:Arial,Helvetica,sans-serif;'
        'font-size:14px;line-height:21px;color:#243229;">'
        f"{text_to_html(content)}</div>{_signature_html(signature)}"
    )
    return OutboundRenderResult(body_text=final_text, body_html=final_html)


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
    outbound = render_outbound_email(rendered_body, organization=organization)
    return RenderResult(
        subject=rendered_subject,
        body_text=rendered_body,
        body_html=outbound.body_html,
        missing_variables=missing,
        unknown_variables=unknown,
    )
