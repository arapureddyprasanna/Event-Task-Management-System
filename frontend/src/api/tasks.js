import api from './client';

export const eventTasks = (eventId, params = {}) => api.get(`/api/events/${eventId}/tasks/`, { params });
export const myTasks = (params = {}) => api.get('/api/tasks/my/', { params });
export const getTask = (id) => api.get(`/api/tasks/${id}/`);
export const updateTask = (id, values) => api.patch(`/api/tasks/${id}/`, values);
export const createEventTask = (eventId, values) => api.post(`/api/events/${eventId}/tasks/`, values);
