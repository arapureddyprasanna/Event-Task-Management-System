import api from './client';

export const listUsers = (params = {}) => api.get('/api/users/', { params });
export const getUser = (id) => api.get(`/api/users/${id}/`);
export const setUserActive = (id, isActive) => api.patch(`/api/users/${id}/activation/`, { is_active: isActive });
