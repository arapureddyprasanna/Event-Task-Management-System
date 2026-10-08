import api from './client';

export const register = (values) => api.post('/api/auth/register/', values);
export const createAdmin = (values) => api.post('/api/auth/admin/create/', values);
export const verifyEmail = ({ email, otp }) => api.post('/api/auth/verify-email/', { email, otp });
export const resendOtp = ({ email }) => api.post('/api/auth/resend-otp/', { email });
export const login = (values) => api.post('/api/auth/login/', values);
export const refreshToken = (refresh) => api.post('/api/auth/token/refresh/', { refresh }, { skipAuthRefresh: true });
export const logout = (refresh) => api.post('/api/auth/logout/', { refresh });
export const forgotPassword = (email) => api.post('/api/auth/forgot-password/', { email });
export const resetPassword = (values) => api.post('/api/auth/reset-password/', values);
export const getProfile = () => api.get('/api/auth/profile/');
export const updateProfile = (values) => api.patch('/api/auth/profile/', values);
export const changePassword = (values) => api.post('/api/auth/change-password/', values);
