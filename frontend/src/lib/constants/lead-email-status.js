export const LEAD_EMAIL_STATUS = Object.freeze({
  NONE: 'none',
  DRAFT: 'draft',
  SENT: 'sent',
  REPLIED: 'replied',
  FOLLOW_UP: 'follow_up'
});

export const LEAD_EMAIL_STATUS_OPTIONS = Object.freeze([
  { value: LEAD_EMAIL_STATUS.DRAFT, label: 'Concept' },
  { value: LEAD_EMAIL_STATUS.SENT, label: 'Verzonden' },
  { value: LEAD_EMAIL_STATUS.REPLIED, label: 'Reactie ontvangen' },
  { value: LEAD_EMAIL_STATUS.FOLLOW_UP, label: 'Follow-up nodig' },
  { value: LEAD_EMAIL_STATUS.NONE, label: 'Geen e-mailactiviteit' }
]);

const LEAD_EMAIL_STATUS_STYLES = Object.freeze({
  [LEAD_EMAIL_STATUS.DRAFT]: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
  [LEAD_EMAIL_STATUS.SENT]: 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300',
  [LEAD_EMAIL_STATUS.REPLIED]:
    'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
  [LEAD_EMAIL_STATUS.FOLLOW_UP]: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
});

/** @param {string|null|undefined} value */
function formatEmailDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('nl-NL', {
    day: 'numeric',
    month: 'short'
  })
    .format(date)
    .replace('.', '');
}

/**
 * Return all presentation data for one lead email-status badge.
 * @param {string} status
 * @param {{ draftCount?: number, lastEmailAt?: string|null }} [activity]
 */
export function getLeadEmailStatusPresentation(status, activity = {}) {
  const { draftCount = 0, lastEmailAt = null } = activity;
  const date = formatEmailDate(lastEmailAt);

  if (status === LEAD_EMAIL_STATUS.DRAFT) {
    return {
      icon: 'draft',
      label: draftCount > 1 ? `${draftCount} concepten` : 'Concept',
      title: `${draftCount} e-mailconcept${draftCount === 1 ? '' : 'en'} klaar`,
      classes: LEAD_EMAIL_STATUS_STYLES[status]
    };
  }
  if (status === LEAD_EMAIL_STATUS.SENT) {
    return {
      icon: 'sent',
      label: date ? `Verzonden · ${date}` : 'Verzonden',
      title: `E-mail verzonden${date ? ` op ${date}` : ''}`,
      classes: LEAD_EMAIL_STATUS_STYLES[status]
    };
  }
  if (status === LEAD_EMAIL_STATUS.REPLIED) {
    return {
      icon: 'replied',
      label: date ? `Reactie · ${date}` : 'Reactie ontvangen',
      title: `Reactie ontvangen${date ? ` op ${date}` : ''}`,
      classes: LEAD_EMAIL_STATUS_STYLES[status]
    };
  }
  if (status === LEAD_EMAIL_STATUS.FOLLOW_UP) {
    return {
      icon: 'follow_up',
      label: 'Follow-up nodig',
      title: `Opvolging nodig${date ? ` na e-mail van ${date}` : ''}`,
      classes: LEAD_EMAIL_STATUS_STYLES[status]
    };
  }
  return null;
}
