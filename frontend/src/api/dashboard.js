import api from './client';

export const getUserDashboard = () => api.get('/api/dashboard/');
export const getAdminDashboard = () => api.get('/api/admin/dashboard/');
