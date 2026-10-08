import axios from 'axios';

const baseURL = (process.env.REACT_APP_API_URL || '').replace(/\/+$/, '');

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
});

export const sessionKeys = {
  access: 'gather.access',
  refresh: 'gather.refresh',
};

export function clearSessionTokens() {
  window.sessionStorage.removeItem(sessionKeys.access);
  window.sessionStorage.removeItem(sessionKeys.refresh);
}

api.interceptors.request.use((config) => {
  const access = window.sessionStorage.getItem(sessionKeys.access);
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

let refreshRequest;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status !== 401
      || !original
      || original.skipAuthRefresh
      || /\/auth\/(login|register|verify-email|forgot-password|reset-password|token\/refresh)\//.test(original.url || '')
    ) {
      return Promise.reject(error);
    }
    if (original._retry) {
      clearSessionTokens();
      window.dispatchEvent(new Event('gather:session-expired'));
      return Promise.reject(error);
    }

    const refresh = window.sessionStorage.getItem(sessionKeys.refresh);
    if (!refresh) return Promise.reject(error);

    original._retry = true;
    try {
      if (!refreshRequest) {
        refreshRequest = axios.post(
          `${baseURL}/api/auth/token/refresh/`,
          { refresh },
          { timeout: 20000, headers: { 'Content-Type': 'application/json' } },
        ).then(({ data }) => {
          window.sessionStorage.setItem(sessionKeys.access, data.access);
          if (data.refresh) window.sessionStorage.setItem(sessionKeys.refresh, data.refresh);
          return data.access;
        }).finally(() => {
          refreshRequest = undefined;
        });
      }
      const access = await refreshRequest;
      original.headers.Authorization = `Bearer ${access}`;
      return api(original);
    } catch (refreshError) {
      clearSessionTokens();
      window.dispatchEvent(new Event('gather:session-expired'));
      return Promise.reject(refreshError);
    }
  },
);

export function getApiFieldErrors(error) {
  const data = error.response?.data;
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
  return Object.fromEntries(
    Object.entries(data)
      .filter(([, messages]) => Array.isArray(messages) || typeof messages === 'string')
      .map(([field, messages]) => [field, Array.isArray(messages) ? messages.join(' ') : messages]),
  );
}

export function getApiErrorMessage(error) {
  if (!error.response) return 'Unable to connect to the server. Make sure Django is running.';
  const { status, data } = error.response;
  if (typeof data?.detail === 'string') return data.detail;
  const firstError = Object.values(getApiFieldErrors(error))[0];
  if (firstError) return firstError;
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to do that.';
  if (status === 404) return 'That item could not be found.';
  if (status === 409) return 'This change conflicts with the current record. Refresh and try again.';
  if (status >= 500) return 'Something went wrong on the server. Please try again shortly.';
  return 'Please check the information and try again.';
}

export default api;
