import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid thread id' }, { status: 400 });
  try {
    return json(
      await apiRequest(
        `/communications/threads/${params.id}/drafts/`,
        {},
        { cookies, org: locals.org }
      )
    );
  } catch (err) {
    return json({ error: err?.message || 'Concepten laden mislukt' }, { status: 400 });
  }
}

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies, locals }) {
  if (!UUID_RE.test(params.id)) return json({ error: 'Invalid thread id' }, { status: 400 });
  const body = await request.json().catch(() => ({}));
  try {
    return json(
      await apiRequest(
        `/communications/threads/${params.id}/drafts/`,
        { method: 'POST', body },
        { cookies, org: locals.org }
      ),
      { status: 201 }
    );
  } catch (err) {
    return json({ error: err?.message || 'Concept maken mislukt' }, { status: 400 });
  }
}
