export const LEAD_FILTER_KEYS = Object.freeze([
  'search',
  'status',
  'source',
  'rating',
  'email_status',
  'zzp_likelihood',
  'assigned_to',
  'tags',
  'created_at_gte',
  'created_at_lte'
]);

/** @param {URLSearchParams} searchParams */
export function parseLeadFilters(searchParams) {
  return {
    search: searchParams.get('search') || '',
    status: searchParams.get('status') || '',
    source: searchParams.get('source') || '',
    rating: searchParams.get('rating') || '',
    email_status: searchParams.get('email_status') || '',
    zzp_likelihood: searchParams.get('zzp_likelihood') || '',
    assigned_to: searchParams.getAll('assigned_to'),
    tags: searchParams.getAll('tags'),
    created_at_gte: searchParams.get('created_at_gte') || '',
    created_at_lte: searchParams.get('created_at_lte') || ''
  };
}

/**
 * Build lead API query parameters shared by table and kanban views.
 * @param {ReturnType<typeof parseLeadFilters>} filters
 * @param {{ page?: number, limit?: number, includeStatus?: boolean }} [options]
 */
export function buildLeadApiQueryParams(filters, options = {}) {
  const { page, limit, includeStatus = true } = options;
  const params = new URLSearchParams();

  if (page !== undefined && limit !== undefined) {
    params.set('limit', limit.toString());
    params.set('offset', ((page - 1) * limit).toString());
  }
  if (filters.search) params.set('search', filters.search);
  if (includeStatus && filters.status) {
    params.set('status', filters.status.toLowerCase().replace(/_/g, ' '));
  }
  if (filters.source) params.set('source', filters.source.toLowerCase());
  if (filters.rating) params.set('rating', filters.rating);
  if (filters.email_status) params.set('email_status', filters.email_status);
  if (filters.zzp_likelihood) {
    params.set('cf_partner_zzp_likelihood', filters.zzp_likelihood);
  }
  filters.assigned_to.forEach((id) => params.append('assigned_to', id));
  filters.tags.forEach((id) => params.append('tags', id));
  if (filters.created_at_gte) params.set('created_at__gte', filters.created_at_gte);
  if (filters.created_at_lte) params.set('created_at__lte', filters.created_at_lte);

  return params;
}

/** @param {ReturnType<typeof parseLeadFilters>} filters */
export function countActiveLeadFilters(filters) {
  return [
    filters.search,
    filters.source,
    filters.rating,
    filters.email_status,
    filters.zzp_likelihood,
    filters.assigned_to.length > 0,
    filters.tags.length > 0,
    filters.created_at_gte || filters.created_at_lte
  ].filter(Boolean).length;
}
