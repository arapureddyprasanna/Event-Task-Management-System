import api from './client';

export const listNotifications = (params = {}) => api.get('/api/notifications/', { params });
export const markNotificationRead = (id) => api.post(`/api/notifications/${id}/read/`);
export const markAllNotificationsRead = () => api.post('/api/notifications/read-all/');
