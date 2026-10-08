import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

function PublicLayout({ children }) {
  const { isAuthenticated, isStaff, signOut } = useAuth();
  const home = isAuthenticated ? (isStaff ? '/admin' : '/dashboard') : '/';
  return (
    <div className="public-shell">
      <header className="public-nav">
        <Link to={home} className="brand"><span className="brand-mark">g.</span><span>gather</span></Link>
        <nav className="public-links" aria-label="Main navigation">
          <NavLink to="/events">Events</NavLink>
          <NavLink to="/about">About</NavLink>
          {isAuthenticated ? (
            <><Link className="button button-dark button-small" to={home}>My space</Link><button className="nav-text-button" type="button" onClick={signOut}>Log out</button></>
          ) : (
            <><Link to="/login">Log in</Link><Link className="button button-dark button-small" to="/register">Get started</Link></>
          )}
        </nav>
      </header>
      {children}
      <footer className="public-footer"><Link className="brand" to={home}><span className="brand-mark">g.</span><span>gather</span></Link><span>Make room for good plans.</span><Link to="/about">About Gather</Link></footer>
    </div>
  );
}

export default PublicLayout;
