import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, cookies, locals }) {
  if (!UUID_RE.test(params.id)) {
    return json({ error: 'Invalid lead id' }, { status: 400 });
  }
  try {
    const response = await apiRequest(
      `/communications/leads/${params.id}/threads/`,
      {},
      { cookies, org: locals.org }
    );
    return json(response);
  } catch (err) {
    return json({ error: err?.message || 'Could not load email threads' }, { status: 400 });
  }
}

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies, locals }) {
  if (!UUID_RE.test(params.id)) {
    return json({ error: 'Invalid lead id' }, { status: 400 });
  }
  const body = await request.json().catch(() => ({}));
  try {
    const response = await apiRequest(
      `/communications/leads/${params.id}/send/`,
      { method: 'POST', body },
      { cookies, org: locals.org }
    );
    return json(response, { status: 201 });
  } catch (err) {
    return json({ error: err?.message || 'Email could not be sent' }, { status: 400 });
  }
}
