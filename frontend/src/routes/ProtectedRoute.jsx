import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LoadingState } from '../components/common/States';

export function PublicRoute() {
  return <Outlet />;
}

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <LoadingState label="Checking your session…" />;
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}

export function RoleRoute({ admin = false }) {
  const { isStaff } = useAuth();
  if (admin && !isStaff) return <Navigate to="/dashboard" replace />;
  if (!admin && isStaff) return <Navigate to="/admin" replace />;
  return <Outlet />;
}

export function SuperuserRoute({ children }) {
  const { isSuperuser } = useAuth();
  return isSuperuser ? children : <Navigate to="/admin" replace />;
}

export function GuestRoute({ children }) {
  const { isAuthenticated, isLoading, isStaff } = useAuth();
  if (isLoading) return <LoadingState label="Checking your session…" />;
  if (isAuthenticated) return <Navigate to={isStaff ? '/admin' : '/dashboard'} replace />;
  return children;
}
