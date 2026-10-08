import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { cancelRegistration, myRegistrations, registerForEvent } from '../../api/registrations';
import { getEvent, listEvents } from '../../api/events';
import EventCard, { formatDate } from '../../components/events/EventCard';
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, StatusPill } from '../../components/common/States';
import PublicLayout from '../../components/layout/PublicLayout';
import { useAuth } from '../../context/AuthContext';
import { getApiErrorMessage } from '../../api/client';
import toast from 'react-hot-toast';

function EventGrid({ events }) {
  return <div className="event-grid">{events.map((event) => <EventCard event={event} key={event.id} />)}</div>;
}

export function HomePage() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    listEvents({ status: 'published', upcoming: true, page_size: 3 })
      .then(({ data }) => setEvents(data.results || []))
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PublicLayout>
      <main>
        <section className="hero-section">
          <div className="hero-copy"><p className="eyebrow">A little more together</p><h1>Good things happen when we <em>make a plan.</em></h1><p>Find your people, make room for meaningful events, and keep every small detail moving in one calm place.</p><div className="hero-actions"><Link className="button button-dark" to="/events">Explore events <span aria-hidden="true">↗</span></Link><Link className="text-link" to="/about">Get to know Gather</Link></div><div className="hero-note"><span className="hero-note-mark">✳</span><span>From the first idea to the final detail.</span></div></div>
          <div className="hero-visual" aria-label="Gathering around a shared event plan"><div className="hero-sun" /><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="hero-leaf leaf-one" /><div className="hero-leaf leaf-two" /><div className="hero-center-card"><span className="hero-card-overline">A weekend well spent</span><strong>Make the<br />moment matter.</strong><span className="hero-card-line" /><small>Ideas, plans & people in one place</small></div><span className="hero-decoration decor-top">gather<br />your people</span><span className="hero-decoration decor-bottom">good plans<br />grow here</span></div>
        </section>
        <section className="intro-band"><div><span className="intro-number">01</span><p>Less chasing details.<br /><strong>More being there.</strong></p></div><p>Gather brings event plans and the tasks behind them together, so everyone can focus on the part that matters: showing up for each other.</p><Link className="arrow-link" to="/about">A little about us <span aria-hidden="true">↗</span></Link></section>
        <section className="public-section" id="events"><div className="section-heading"><div><p className="eyebrow">Find your next reason</p><h2>Events worth<br /><em>looking forward to.</em></h2></div><Link className="arrow-link" to="/events">See all events <span aria-hidden="true">↗</span></Link></div>{loading ? <LoadingState label="Finding events…" /> : error ? <ErrorState message={error} /> : events.length ? <EventGrid events={events} /> : <EmptyState title="The calendar is taking shape">Check back soon for events to explore.</EmptyState>}</section>
        <section className="feature-section"><div className="section-heading"><div><p className="eyebrow">Make it happen, together</p><h2>One shared plan.<br /><em>Many hands.</em></h2></div><p>Good events are made from small moments of care. Gather gives each one a place.</p></div><div className="feature-grid"><article><span>01</span><h3>Find your people</h3><p>Discover gatherings that bring your community together.</p></article><article><span>02</span><h3>Make a clear plan</h3><p>Keep the event details easy to find and share.</p></article><article><span>03</span><h3>Move the details forward</h3><p>Give each task an owner, a priority, and a next step.</p></article></div></section>
        <section className="how-section"><p className="eyebrow">A simple way to get there</p><h2>From “we should”<br />to <em>“that was lovely.”</em></h2><div className="how-steps"><div><b>01</b><span>Find an event or start one of your own.</span></div><div><b>02</b><span>Bring your people into the plan.</span></div><div><b>03</b><span>Share the work and enjoy the day.</span></div></div></section>
        <section className="cta-section"><div><p className="eyebrow">Your next good plan starts here</p><h2>Make space for<br /><em>something memorable.</em></h2></div><Link className="button button-light" to="/register">Create your account <span aria-hidden="true">↗</span></Link></section>
      </main>
    </PublicLayout>
  );
}

export function AboutPage() {
  return <PublicLayout><main className="public-page about-page"><p className="eyebrow">A place to bring it together</p><h1>Plans are better<br />when they’re <em>shared.</em></h1><p className="about-lede">Gather helps people make events happen with less back-and-forth and more room to enjoy the moment.</p><div className="about-columns"><article><span>01 / THE IDEA</span><h2>Make the details feel lighter.</h2><p>Event details, registrations, and the tasks that move a plan forward belong in the same space. Gather keeps the practical bits close without making them the whole story.</p></article><article><span>02 / THE PEOPLE</span><h2>Everyone has a part to play.</h2><p>Organizers can shape the plan and share tasks. Attendees can follow along, register, and see the work assigned to them.</p></article></div><Link className="button button-dark" to="/events">Find an event <span aria-hidden="true">↗</span></Link></main></PublicLayout>;
}

export function EventsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('published');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = (nextPage = page) => {
    setLoading(true);
    setError('');
    listEvents({ search: search || undefined, status: status || undefined, upcoming: status === 'published' ? true : undefined, page: nextPage, page_size: 9 })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (event) => { event.preventDefault(); load(1); };

  return <PublicLayout><main className="public-page event-browser"><PageHeader eyebrow="The community calendar" title="Find your next gathering.">Browse what’s happening and make a little room for something good.</PageHeader><form className="filter-bar public-filter" onSubmit={submit}><label className="search-control"><span className="sr-only">Search events</span><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search events, places, ideas…" /></label><label className="select-control"><span className="sr-only">Event status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="published">Published events</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label><button className="button button-dark" type="submit">Search</button></form>{loading ? <LoadingState label="Loading events…" /> : error ? <ErrorState message={error} onRetry={() => load(1)} /> : payload?.results?.length ? <><EventGrid events={payload.results} /><Pagination page={page} pages={Math.ceil(payload.count / 9)} onChange={load} /></> : <EmptyState title="No events match yet">Try another search, or check back when the calendar has something new.</EmptyState>}</main></PublicLayout>;
}

export function EventDetailPage() {
  const { id } = useParams();
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [registration, setRegistration] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getEvent(id).then(({ data }) => { if (alive) setEvent(data); })
      .catch((requestError) => { if (alive) setError(getApiErrorMessage(requestError)); })
      .finally(() => { if (alive) setLoading(false); });
    if (isAuthenticated) {
      const findRegistration = async (page = 1) => {
        const { data } = await myRegistrations({ page, page_size: 100 });
        const found = data.results?.find((item) => item.event.id === Number(id));
        if (found || !data.next) return found || null;
        return findRegistration(page + 1);
      };
      findRegistration().then((item) => { if (alive) setRegistration(item); })
        .catch((requestError) => { if (alive) setError(getApiErrorMessage(requestError)); });
    } else setRegistration(null);
    return () => { alive = false; };
  }, [id, isAuthenticated]);

  const submitRegistration = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/events/${id}` } });
      return;
    }
    if (registration?.status === 'registered' && !window.confirm('Cancel your registration for this event?')) return;
    setBusy(true);
    setBusy(true);
    try {
      if (registration?.status === 'registered') {
        const { data } = await cancelRegistration(id);
        setRegistration(data);
        setEvent((current) => ({ ...current, ...data.event }));
        toast.success('Your registration has been cancelled.');
      } else {
        const { data } = await registerForEvent(id);
        setRegistration(data);
        setEvent((current) => ({ ...current, ...data.event }));
        toast.success('You’re registered. We’ll see you there.');
      }
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return <PublicLayout><main className="public-page event-detail-page">{loading ? <LoadingState label="Loading event…" /> : error && !event ? <ErrorState message={error} /> : event ? <><Link className="back-link" to="/events">← All events</Link><div className="detail-cover"><span>GATHER<br />TOGETHER</span><span className="detail-cover-mark">✳</span></div><article className="event-detail"><div className="detail-main"><div className="event-card-meta"><span>{event.location}</span><StatusPill>{event.availability || event.status}</StatusPill></div><h1>{event.title}</h1><p className="detail-description">{event.description}</p><div className="detail-info-grid"><div><span>WHEN</span><strong>{formatDate(event.start_at)}</strong></div><div><span>UNTIL</span><strong>{formatDate(event.end_at)}</strong></div><div><span>WHERE</span><strong>{event.location}</strong></div><div><span>REGISTRATIONS</span><strong>{event.registration_count} active</strong></div><div><span>CAPACITY</span><strong>{event.capacity == null ? 'Unlimited' : `${event.remaining_seats} seats remaining of ${event.capacity}`}</strong></div></div><section className="organizer-card"><div className="avatar">{(event.organizer?.first_name || event.organizer?.username || 'O').slice(0, 1).toUpperCase()}</div><div><span>ORGANIZED BY</span><strong>{[event.organizer?.first_name, event.organizer?.last_name].filter(Boolean).join(' ') || event.organizer?.username}</strong></div></section></div><aside className="detail-action-card"><p className="eyebrow">Save your place</p><h2>Be part of it.</h2>{registration?.status === 'registered' ? <div className="registration-status"><StatusPill>registered</StatusPill><p>You’re on the list. Looking forward to it.</p></div> : <p className="card-description">Join the gathering and keep the event details close.</p>}{isAuthenticated && <p className="muted-note">You’re signed in as <strong>{user?.username}</strong>; registration will use this account.</p>}{(event.availability === 'available' || registration?.status === 'registered') ? <button className="button button-dark button-wide" type="button" onClick={submitRegistration} disabled={busy || (isAuthenticated && !user?.is_email_verified && !user?.registration_demo_access)}>{busy ? 'Updating…' : registration?.status === 'registered' ? 'Cancel registration' : 'Register for event'}</button> : <p className="muted-note">Registration {event.availability?.replaceAll('_', ' ') || 'is closed'}.</p>}{isAuthenticated && !user?.is_email_verified && !user?.registration_demo_access && <p className="muted-note">Verify your email to register.</p>}<p className="muted-note">{event.remaining_seats == null ? 'Unlimited capacity.' : `${event.remaining_seats} seats remaining.`}</p></aside></article></> : null}</main></PublicLayout>;
}
