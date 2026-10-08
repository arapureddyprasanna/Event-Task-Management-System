import api from './client';

export const myRegistrations = (params = {}) => api.get('/api/events/my-registrations/', { params });
export const eventRegistrations = (eventId, params = {}) =>
  api.get(`/api/events/${eventId}/registrations/`, { params });
export const registerForEvent = (eventId) => api.post(`/api/events/${eventId}/register/`, {});
export const cancelRegistration = (eventId) => api.post(`/api/events/${eventId}/register/cancel/`, {});
