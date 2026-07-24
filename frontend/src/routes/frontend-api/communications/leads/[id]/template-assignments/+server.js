import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid lead id' }, { status: 400 });
  try {
    return json(
      await apiRequest(
        `/communications/leads/${params.id}/template-assignments/`,
        {},
        { cookies, org: locals.org }
      )
    );
  } catch (err) {
    return json({ error: err?.message || 'Toewijzingen laden mislukt' }, { status: 400 });
  }
}

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid lead id' }, { status: 400 });
  const body = await request.json().catch(() => ({}));
  try {
    return json(
      await apiRequest(
        `/communications/leads/${params.id}/template-assignments/`,
        { method: 'POST', body },
        { cookies, org: locals.org }
      )
    );
  } catch (err) {
    return json({ error: err?.message || 'Toewijzing opslaan mislukt' }, { status: 400 });
  }
}
