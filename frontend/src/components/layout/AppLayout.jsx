import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { listNotifications } from '../../api/notifications';

const userLinks = [
  ['/dashboard', 'Overview', '⌂'],
  ['/events', 'Discover events', '✳'],
  ['/my/registrations', 'My registrations', '▤'],
  ['/my/tasks', 'My tasks', '✓'],
  ['/notifications', 'Notifications', '◌'],
  ['/history', 'History', '↺'],
  ['/profile', 'Profile', '○'],
];
const adminLinks = [
  ['/admin', 'Overview', '⌂'],
  ['/admin/users', 'Users', '♙'],
  ['/admin/events', 'Events', '✳'],
  ['/admin/tasks', 'Tasks', '✓'],
  ['/admin/registrations', 'Registrations', '▤'],
  ['/admin/notifications', 'Notifications', '◌'],
  ['/admin/history', 'History', '↺'],
  ['/admin/profile', 'Profile', '○'],
];

function AppLayout({ admin = false }) {
  const { user, isSuperuser, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const navigate = useNavigate();
  const links = admin
    ? [...adminLinks, ...(isSuperuser ? [['/admin/add-admin', 'Add Admin', '＋'], ['/admin/access-requests', 'Admin access requests', '♙']] : [])]
    : userLinks;
  const closeMenu = () => setMenuOpen(false);

  const loadUnreadCount = useCallback(() => {
    listNotifications({ unread: 'true', page_size: 1 })
      .then(({ data }) => setUnreadCount(data.count || 0))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadUnreadCount();
    const refresh = () => loadUnreadCount();
    window.addEventListener('gather:notifications-changed', refresh);
    window.addEventListener('focus', refresh);
    const timer = window.setInterval(loadUnreadCount, 60000);
    return () => {
      window.removeEventListener('gather:notifications-changed', refresh);
      window.removeEventListener('focus', refresh);
      window.clearInterval(timer);
    };
  }, [loadUnreadCount]);

  const handleSignOut = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className={`workspace ${admin ? 'workspace-admin' : ''}`}>
      <aside className={`sidebar${menuOpen ? ' sidebar-open' : ''}`}>
        <NavLink to={admin ? '/admin' : '/dashboard'} className="brand sidebar-brand" onClick={closeMenu}>
          <span className="brand-mark">g.</span><span>gather</span>
        </NavLink>
        <p className="sidebar-label">{admin ? 'WORKSPACE' : 'YOUR SPACE'}</p>
        <nav className="side-links" aria-label={admin ? 'Admin navigation' : 'User navigation'}>
          {links.map(([to, label, icon]) => (
            <NavLink end={to === '/dashboard' || to === '/admin'} to={to} key={to} onClick={closeMenu}>
              <span aria-hidden="true">{icon}</span>{label}{label === 'Notifications' && unreadCount > 0 && <span className="notification-count" aria-label={`${unreadCount} unread notifications`}>{unreadCount}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="avatar" aria-hidden="true">{(user?.first_name || user?.username || 'G').slice(0, 1).toUpperCase()}</div>
          <div className="sidebar-user"><strong>{user?.first_name ? `${user.first_name} ${user.last_name || ''}` : user?.username}</strong><span>{admin ? 'Administrator' : 'Member'}</span></div>
          <button className="logout-button" type="button" aria-label="Logout" title="Logout" onClick={() => window.confirm('Are you sure you want to log out?') && handleSignOut()}><span aria-hidden="true">↗</span><span>Logout</span></button>
        </div>
      </aside>
      {menuOpen && <button type="button" className="sidebar-scrim" aria-label="Close navigation" onClick={closeMenu} />}
      <div className="workspace-main">
        <header className="workspace-topbar">
          <button type="button" className="menu-toggle" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>☰</button>
          <span className="topbar-context">{admin ? 'ADMIN WORKSPACE' : 'EVENT SPACE'}</span>
          <button className="topbar-profile" type="button" onClick={() => navigate(admin ? '/admin/profile' : '/profile')}>
            <span className="avatar avatar-small" aria-hidden="true">{(user?.first_name || user?.username || 'G').slice(0, 1).toUpperCase()}</span>
            <span>{user?.first_name || user?.username}</span>
          </button>
        </header>
        <main className="workspace-content"><Outlet /></main>
      </div>
    </div>
  );
}

export default AppLayout;
