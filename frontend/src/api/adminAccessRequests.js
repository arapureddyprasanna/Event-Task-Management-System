import api from './client';

export const listAdminAccessRequests = (params = {}) =>
  api.get('/api/auth/admin-requests/', { params });
export const approveAdminAccessRequest = (id, reason = '') =>
  api.post(`/api/auth/admin-requests/${id}/approve/`, { reason });
export const rejectAdminAccessRequest = (id, reason = '') =>
  api.post(`/api/auth/admin-requests/${id}/reject/`, { reason });
