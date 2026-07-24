import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid thread id' }, { status: 400 });
  try {
    return json(
      await apiRequest(`/communications/threads/${params.id}/`, {}, { cookies, org: locals.org })
    );
  } catch (err) {
    return json({ error: err?.message || 'Thread laden mislukt' }, { status: 400 });
  }
}
