import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function PATCH({ params, request, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid draft id' }, { status: 400 });
  const body = await request.json().catch(() => ({}));
  try {
    return json(
      await apiRequest(
        `/communications/drafts/${params.id}/`,
        { method: 'PATCH', body },
        { cookies, org: locals.org }
      )
    );
  } catch (err) {
    return json({ error: err?.message || 'Concept opslaan mislukt' }, { status: 400 });
  }
}
