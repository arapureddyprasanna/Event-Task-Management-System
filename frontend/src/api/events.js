import api from './client';

export const listEvents = (params = {}) => api.get('/api/events/', { params });
export const getEvent = (id) => api.get(`/api/events/${id}/`);
export const createEvent = (values) => api.post('/api/events/', values);
export const updateEvent = (id, values) => api.patch(`/api/events/${id}/`, values);
