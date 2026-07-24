import { json } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies, locals }) {
  if (!UUID_RE.test(params.id)) {
    return json({ error: 'Invalid thread id' }, { status: 400 });
  }
  const body = await request.json().catch(() => ({}));
  try {
    const response = await apiRequest(
      `/communications/threads/${params.id}/reply/`,
      { method: 'POST', body },
      { cookies, org: locals.org }
    );
    return json(response, { status: 201 });
  } catch (err) {
    return json({ error: err?.message || 'Reply could not be sent' }, { status: 400 });
  }
}
