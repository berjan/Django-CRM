import { error, fail, redirect } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

function requireAdmin(profile) {
  if (profile?.role !== 'ADMIN' && !profile?.is_organization_admin) {
    throw error(403, 'Only admins can manage lead email');
  }
}

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, locals, url }) {
  requireAdmin(locals.profile);

  const oauthError = url.searchParams.get('error');
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');

  if (oauthError) {
    throw redirect(303, `/settings/email?oauth_error=${encodeURIComponent(oauthError)}`);
  }

  if (code && state) {
    try {
      await apiRequest(
        '/communications/gmail/callback/',
        { method: 'POST', body: { code, state } },
        { cookies, org: locals.org }
      );
    } catch (err) {
      throw redirect(
        303,
        `/settings/email?oauth_error=${encodeURIComponent(err?.message || 'Connection failed')}`
      );
    }
    throw redirect(303, '/settings/email?connected=1');
  }

  try {
    const response = await apiRequest(
      '/communications/mailboxes/',
      {},
      { cookies, org: locals.org }
    );
    return {
      configured: response.configured,
      mailboxes: response.mailboxes || [],
      connected: url.searchParams.get('connected') === '1',
      oauthError: url.searchParams.get('oauth_error') || ''
    };
  } catch (err) {
    console.error('Failed to load Gmail settings:', err);
    throw error(500, 'Failed to load lead email settings');
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  connect: async ({ cookies, locals }) => {
    requireAdmin(locals.profile);
    try {
      const response = await apiRequest(
        '/communications/gmail/connect/',
        { method: 'POST' },
        { cookies, org: locals.org }
      );
      throw redirect(303, response.authorization_url);
    } catch (err) {
      if (err?.status === 303) throw err;
      return fail(400, { error: err?.message || 'Could not start Gmail connection' });
    }
  },

  sync: async ({ request, cookies, locals }) => {
    requireAdmin(locals.profile);
    const data = await request.formData();
    const id = String(data.get('id') || '');
    if (!id) return fail(400, { error: 'Missing mailbox id' });
    try {
      const response = await apiRequest(
        `/communications/mailboxes/${id}/sync/`,
        { method: 'POST' },
        { cookies, org: locals.org }
      );
      return { success: true, synced: response.ingested || 0 };
    } catch (err) {
      return fail(400, { error: err?.message || 'Mailbox sync failed' });
    }
  },

  disconnect: async ({ request, cookies, locals }) => {
    requireAdmin(locals.profile);
    const data = await request.formData();
    const id = String(data.get('id') || '');
    if (!id) return fail(400, { error: 'Missing mailbox id' });
    try {
      await apiRequest(
        `/communications/mailboxes/${id}/disconnect/`,
        { method: 'DELETE' },
        { cookies, org: locals.org }
      );
      return { success: true, disconnected: true };
    } catch (err) {
      return fail(400, { error: err?.message || 'Mailbox disconnect failed' });
    }
  }
};
