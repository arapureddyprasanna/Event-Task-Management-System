import { Navigate, Route, Routes } from 'react-router-dom';
import RegisterPage from '../pages/Register/RegisterPage';
import VerifyEmailPage from '../pages/VerifyEmail/VerifyEmailPage';
import AppLayout from '../components/layout/AppLayout';
import { GuestRoute, ProtectedRoute, PublicRoute, RoleRoute, SuperuserRoute } from './ProtectedRoute';
import { AboutPage, EventDetailPage, EventsPage, HomePage } from '../pages/public/PublicPages';
import { ForgotPasswordPage, LoginPage, ResetPasswordPage } from '../pages/auth/AuthPages';
import { DashboardPage, HistoryPage, MyRegistrationsPage, MyTasksPage, NotificationsPage } from '../pages/user/UserPages';
import ProfilePage from '../pages/profile/ProfilePage';
import { AdminDashboardPage, AdminEventsPage, AdminRegistrationsPage, AdminUsersPage } from '../pages/admin/AdminPages';
import AdminTasksPage from '../pages/admin/AdminTaskManager';
import AdminAccessRequestsPage from '../pages/admin/AdminAccessRequestsPage';
import CreateAdminPage from '../pages/admin/CreateAdminPage';

function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/events/:id" element={<EventDetailPage />} />
      </Route>
      <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
      <Route path="/forgot-password" element={<GuestRoute><ForgotPasswordPage /></GuestRoute>} />
      <Route path="/reset-password" element={<GuestRoute><ResetPasswordPage /></GuestRoute>} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<RoleRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/my/registrations" element={<MyRegistrationsPage />} />
            <Route path="/my/tasks" element={<MyTasksPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
        <Route element={<RoleRoute admin />}>
          <Route element={<AppLayout admin />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/events" element={<AdminEventsPage />} />
            <Route path="/admin/tasks" element={<AdminTasksPage />} />
            <Route path="/admin/registrations" element={<AdminRegistrationsPage />} />
            <Route path="/admin/access-requests" element={<SuperuserRoute><AdminAccessRequestsPage /></SuperuserRoute>} />
            <Route path="/admin/add-admin" element={<SuperuserRoute><CreateAdminPage /></SuperuserRoute>} />
            <Route path="/admin/notifications" element={<NotificationsPage />} />
            <Route path="/admin/history" element={<HistoryPage />} />
            <Route path="/admin/profile" element={<ProfilePage admin />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default AppRoutes;
