import api from './client';

export const listActivity = (params = {}) => api.get('/api/activity/', { params });
