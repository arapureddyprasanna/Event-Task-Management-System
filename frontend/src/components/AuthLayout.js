import { Link, useLocation } from 'react-router-dom';

function AuthLayout({ children, pageLabel, title, titleAccent, description }) {
  const location = useLocation();
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="Gather home"><span className="brand-mark" aria-hidden="true">g.</span><span>gather</span></Link>
        <p className="topbar-note">{location.pathname === '/verify-email' ? 'Step 2 of 2 · Email verification' : 'A calmer way to plan together'}</p>
      </header>
      <main className="auth-layout">
        <section className="intro-panel" aria-labelledby="intro-title">
          <p className="eyebrow">{pageLabel}</p>
          <h1 id="intro-title">{title} <em>{titleAccent}</em></h1>
          <p className="intro-copy">{description}</p>
          <div className="auth-points"><span><i>01</i> Events worth sharing</span><span><i>02</i> Plans that feel clear</span><span><i>03</i> Details that move forward</span></div>
        </section>
        <section className="auth-card" aria-label={pageLabel}>{children}</section>
      </main>
      <footer className="page-footer">A little more together, one plan at a time.</footer>
    </div>
  );
}

export default AuthLayout;
