import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAdminDashboard } from '../../api/dashboard';
import { createEvent, listEvents, updateEvent } from '../../api/events';
import { eventRegistrations } from '../../api/registrations';
import { listUsers, getUser, setUserActive } from '../../api/users';
import { getApiErrorMessage } from '../../api/client';
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, StatusPill } from '../../components/common/States';
import { formatDate } from '../../components/events/EventCard';
import toast from 'react-hot-toast';

export function AdminDashboardPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    setLoading(true); setError('');
    getAdminDashboard().then(({ data }) => setSummary(data))
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  }, [reload]);
  return <><PageHeader eyebrow="Admin workspace" title="The whole picture.">A clear view of your community and the events bringing it together.</PageHeader>{loading ? <LoadingState label="Loading workspace data…" /> : error ? <ErrorState message={error} onRetry={() => setReload((value) => value + 1)} /> : summary && <><div className="stat-grid admin-stat-grid"><StatCard label="Community members" value={summary.users.total} detail="Accounts in the system" icon="♙" /><StatCard label="Events" value={summary.events.total} detail={`${summary.events.published} published`} icon="✳" /><StatCard label="Registrations" value={summary.registrations.total} detail={`${summary.registrations.active} active`} icon="▤" /><StatCard label="Tasks" value={summary.tasks.total} detail={`${summary.tasks.pending} pending · ${summary.tasks.in_progress} in progress`} icon="✓" /><StatCard label="Completed tasks" value={summary.tasks.completed} detail={`${summary.tasks.overdue} overdue`} icon="○" /><StatCard label="Pending access requests" value={summary.pending_admin_access_requests} detail="Awaiting superuser review" icon="♙" /><StatCard label="Unread admin notifications" value={summary.unread_admin_notifications} detail="For staff accounts" icon="◌" /></div><section className="admin-welcome"><div><p className="eyebrow">The details behind the gathering</p><h2>Good work happens<br />when the plan is <em>clear.</em></h2><p>Manage people, events, tasks, and registrations from one workspace.</p></div><div className="welcome-art" aria-hidden="true"><span className="welcome-sun" /><span className="welcome-ring" /><span className="welcome-plant">✳</span></div></section><div className="quick-links admin-quick"><Link to="/admin/events"><span>✳</span><div><strong>Manage events</strong><small>Create an event and guide its lifecycle</small></div><b>↗</b></Link><Link to="/admin/users"><span>♙</span><div><strong>Manage people</strong><small>Search accounts and update activation</small></div><b>↗</b></Link><Link to="/admin/tasks"><span>✓</span><div><strong>Coordinate tasks</strong><small>Assign work to registered attendees</small></div><b>↗</b></Link></div><div className="dashboard-lower"><section className="surface-card"><div className="surface-heading"><div><p className="eyebrow">Coming up</p><h2>Upcoming events</h2></div><Link className="arrow-link" to="/admin/events">Manage events</Link></div>{summary.upcoming_events.length ? summary.upcoming_events.map((event) => <article className="dashboard-feed-item" key={event.id}><strong><Link to={`/events/${event.id}`}>{event.title}</Link></strong><p>{formatDate(event.start_at)} · {event.location} · {event.registration_count} registered{event.remaining_seats == null ? '' : ` · ${event.remaining_seats} seats left`}</p></article>) : <EmptyState title="No upcoming events">Published future events will appear here.</EmptyState>}</section><section className="surface-card"><div className="surface-heading"><div><p className="eyebrow">System history</p><h2>Recent activity</h2></div><Link className="arrow-link" to="/admin/history">See all</Link></div>{summary.recent_activity.length ? summary.recent_activity.map((activity) => <article className="dashboard-feed-item" key={activity.id}><strong>{activity.description}</strong><small>{formatDate(activity.created_at)}</small></article>) : <EmptyState title="No recent activity">System activity will appear here.</EmptyState>}</section></div></>}</>;
}

function StatCard({ label, value, detail, icon }) {
  return <article className="stat-card"><span className="stat-icon" aria-hidden="true">{icon}</span><span className="stat-label">{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

export function AdminUsersPage() {
  const [search, setSearch] = useState('');
  const [active, setActive] = useState('');
  const [verified, setVerified] = useState('');
  const [staff, setStaff] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = (nextPage = page) => {
    setLoading(true); setError('');
    listUsers({ search: search || undefined, is_active: active || undefined, is_email_verified: verified || undefined, is_staff: staff || undefined, page: nextPage, page_size: 20 })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // Load only when the explicit filter changes; search submits on demand.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1);
  }, [active, verified, staff]); // eslint-disable-line react-hooks/exhaustive-deps
  const showUser = async (id) => {
    setSelected({ loading: true });
    try { const { data } = await getUser(id); setSelected(data); }
    catch (requestError) { setError(getApiErrorMessage(requestError)); setSelected(null); }
  };
  const toggleActive = async (user) => {
    const next = !user.is_active;
    if (!next && !window.confirm(`Deactivate ${user.username}? They will no longer be able to sign in.`)) return;
    try { 
      await setUserActive(user.id, next); 
      await load(page); 
      if (selected?.id === user.id) await showUser(user.id);
      toast.success(`Account ${next ? 'activated' : 'deactivated'} successfully.`);
    }
    catch (requestError) { setError(getApiErrorMessage(requestError)); }
  };
  return <><PageHeader eyebrow="People" title="Community members.">Search accounts and manage access using the existing user controls.</PageHeader><form className="filter-bar" onSubmit={(event) => { event.preventDefault(); load(1); }}><label className="search-control"><span aria-hidden="true">⌕</span><span className="sr-only">Search users</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, username, or email" /></label><label className="select-control"><span>Account status</span><select value={active} onChange={(event) => setActive(event.target.value)}><option value="">All accounts</option><option value="true">Active</option><option value="false">Inactive</option></select></label><label className="select-control"><span>Email verification</span><select value={verified} onChange={(event) => setVerified(event.target.value)}><option value="">Any status</option><option value="true">Verified</option><option value="false">Needs verification</option></select></label><label className="select-control"><span>Role</span><select value={staff} onChange={(event) => setStaff(event.target.value)}><option value="">All roles</option><option value="false">Members</option><option value="true">Staff</option></select></label><button className="button button-dark" type="submit">Search</button></form>{error && <div className="inline-alert" role="alert">{error}</div>}{loading ? <LoadingState label="Loading members…" /> : payload?.results?.length ? <><div className="table-wrap"><table className="data-table"><thead><tr><th>Member</th><th>Email</th><th>Role</th><th>Verified</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{payload.results.map((user) => <tr key={user.id}><td><button className="table-link" type="button" onClick={() => showUser(user.id)}>{user.first_name || user.username} {user.last_name}</button><small>@{user.username}</small></td><td>{user.email}</td><td>{user.is_staff ? 'Staff' : 'Member'}</td><td>{user.is_email_verified ? 'Verified' : 'Pending'}</td><td><StatusPill tone={user.is_active ? 'active' : 'inactive'}>{user.is_active ? 'Active' : 'Inactive'}</StatusPill></td><td><button className="button button-quiet button-small" type="button" onClick={() => toggleActive(user)}>{user.is_active ? 'Deactivate' : 'Activate'}</button></td></tr>)}</tbody></table></div><Pagination page={page} pages={Math.ceil(payload.count / 20)} onChange={load} /></> : <EmptyState title="No members found">Try a different search or account filter.</EmptyState>}{selected && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="user-detail-title"><button className="modal-close" type="button" aria-label="Close" onClick={() => setSelected(null)}>×</button>{selected.loading ? <LoadingState label="Loading account…" /> : <><p className="eyebrow">Member profile</p><h2 id="user-detail-title">{selected.first_name || selected.username} {selected.last_name}</h2><dl className="detail-list"><dt>Username</dt><dd>{selected.username}</dd><dt>Email</dt><dd>{selected.email}</dd><dt>Role</dt><dd>{selected.is_staff ? 'Staff' : 'Member'}</dd><dt>Email verification</dt><dd>{selected.is_email_verified ? 'Verified' : 'Not verified'}</dd><dt>Joined</dt><dd>{formatDate(selected.date_joined)}</dd></dl></>}</section></div>}</>;
}

function EventForm({ event, onSave, onCancel, busy }) {
  const [title, setTitle] = useState(event?.title || '');
  const [description, setDescription] = useState(event?.description || '');
  const [location, setLocation] = useState(event?.location || '');
  const toInput = (value) => value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
  const [startAt, setStartAt] = useState(toInput(event?.start_at));
  const [endAt, setEndAt] = useState(toInput(event?.end_at));
  const [capacity, setCapacity] = useState(event?.capacity ?? '');
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault(); setError('');
    const values = { title: title.trim(), description: description.trim(), location: location.trim(), start_at: new Date(startAt).toISOString(), end_at: new Date(endAt).toISOString(), capacity: capacity === '' ? null : Number(capacity) };
    try { await onSave(values); }
    catch (requestError) { setError(getApiErrorMessage(requestError)); }
  };
  return <form className="editor-card" onSubmit={submit}><div className="surface-heading"><div><p className="eyebrow">{event ? 'Edit details' : 'Start something'}</p><h2>{event ? event.title : 'Create an event'}</h2></div><button className="icon-button" type="button" aria-label="Close form" onClick={onCancel}>×</button></div><div className="form-grid"><Field label="Event title"><input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required /></Field><Field label="Location"><input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={255} required /></Field><Field label="Starts"><input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} required /></Field><Field label="Ends"><input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} required /></Field><Field label="Capacity"><input type="number" min="1" value={capacity} onChange={(e) => setCapacity(e.target.value)} placeholder="Unlimited" /></Field><Field label="Description" full><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} required /></Field></div>{error && <div className="inline-alert" role="alert">{error}</div>}<div className="form-actions"><button className="button button-dark" type="submit" disabled={busy}>{busy ? 'Saving…' : event ? 'Save event' : 'Create draft'}</button><button className="button button-quiet" type="button" onClick={onCancel}>Cancel</button></div>{!event && <p className="muted-note">New events begin as drafts. Publish them when they’re ready.</p>}</form>;
}

function Field({ label, children, full = false }) {
  return <label className={`form-field${full ? ' form-field-full' : ''}`}><span>{label}</span>{children}</label>;
}

export function AdminEventsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const load = (nextPage = page) => {
    setLoading(true); setError('');
    listEvents({ search: search || undefined, status: status || undefined, page: nextPage, page_size: 20 })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // Load only when the explicit filter changes; search submits on demand.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  const saveEvent = async (values) => {
    setBusy(true);
    setError('');
    try { 
      if (editor?.id) { await updateEvent(editor.id, values); toast.success('Event updated successfully.'); } 
      else { await createEvent(values); toast.success('Event created successfully.'); } 
      setEditor(null); load(editor?.id ? page : 1); 
    }
    finally { setBusy(false); }
  };
  const transition = async (event, nextStatus) => {
    setBusyId(event.id); setError('');
    try { await updateEvent(event.id, { status: nextStatus }); toast.success(`Event ${nextStatus}.`); load(page); }
    catch (requestError) { toast.error(getApiErrorMessage(requestError)); }
    finally { setBusyId(null); }
  };
  return <><PageHeader eyebrow="Event operations" title="Manage events." action={<button className="button button-dark" type="button" onClick={() => setEditor({})}>＋ Create event</button>}>Create drafts, review event details, and guide each event through its available lifecycle.</PageHeader>{editor && <EventForm event={editor.id ? editor : null} onSave={saveEvent} onCancel={() => setEditor(null)} busy={busy} />}<form className="filter-bar" onSubmit={(e) => { e.preventDefault(); load(1); }}><label className="search-control"><span aria-hidden="true">⌕</span><span className="sr-only">Search events</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search events, places, details" /></label><label className="select-control"><span>Event status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="draft">Draft</option><option value="published">Published</option><option value="cancelled">Cancelled</option><option value="completed">Completed</option></select></label><button className="button button-quiet" type="submit">Search</button></form>{error && <div className="inline-alert" role="alert">{error}</div>}{loading ? <LoadingState label="Loading events…" /> : payload?.results?.length ? <><div className="admin-event-list">{payload.results.map((event) => <article className="admin-event-row" key={event.id}><div className="admin-event-mark">✳</div><div className="admin-event-copy"><div className="event-card-meta"><span>{event.location}</span><StatusPill>{event.status}</StatusPill></div><h2>{event.title}</h2><p>{formatDate(event.start_at)} · {event.capacity == null ? 'Unlimited capacity' : `${event.capacity} places`} · {event.registration_count} registered · {event.availability.replaceAll('_', ' ')}</p><Link to={`/events/${event.id}`} className="text-link">View public details</Link></div><div className="admin-event-actions">{event.status === 'draft' && <button className="button button-dark button-small" type="button" disabled={busyId === event.id} onClick={() => transition(event, 'published')}>Publish</button>}{event.status === 'published' && <><button className="button button-quiet button-small" type="button" onClick={() => setEditor(event)}>Edit</button><button className="button button-quiet button-small" type="button" disabled={busyId === event.id} onClick={() => transition(event, 'completed')}>Complete</button><button className="button button-danger button-small" type="button" disabled={busyId === event.id} onClick={() => window.confirm(`Cancel “${event.title}”?`) && transition(event, 'cancelled')}>Cancel</button></>}{(event.status === 'published' || event.status === 'draft') && <Link className="button button-quiet button-small" to={`/admin/registrations?event=${event.id}`}>Registrations</Link>}</div></article>)}</div><Pagination page={page} pages={Math.ceil(payload.count / 20)} onChange={load} /></> : !error && <EmptyState title="No events here yet">Create a draft when you’re ready to start planning.</EmptyState>}</>;
}

export function AdminRegistrationsPage() {
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState(new URLSearchParams(window.location.search).get('event') || '');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { listEvents({ page_size: 100 }).then(({ data }) => setEvents(data.results || [])).catch((e) => setError(getApiErrorMessage(e))).finally(() => setLoadingEvents(false)); }, []);
  const load = (nextPage = page, nextStatus = status, nextSearch = submittedSearch) => {
    if (!eventId) return;
    setLoadingRows(true); setError('');
    eventRegistrations(eventId, { page: nextPage, page_size: 20, status: nextStatus || undefined, search: nextSearch || undefined })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((e) => setError(getApiErrorMessage(e)))
      .finally(() => setLoadingRows(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (eventId) load(1, status);
  }, [eventId, status, submittedSearch]); // eslint-disable-line react-hooks/exhaustive-deps
  return <><PageHeader eyebrow="Attendee list" title="Registrations.">Review attendee records for an event you manage.</PageHeader><form className="filter-bar" onSubmit={(event) => { event.preventDefault(); setSubmittedSearch(search); if (eventId) load(1, status, search); }}><label className="select-control"><span>Event</span><select value={eventId} onChange={(e) => setEventId(e.target.value)}><option value="">Choose an event</option>{events.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}</select></label><label className="select-control"><span>Registration status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All registrations</option><option value="registered">Registered</option><option value="cancelled">Cancelled</option></select></label><label className="search-control"><span className="sr-only">Search participants</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search participant" /></label><button className="button button-quiet" type="submit">Search</button></form>{loadingEvents ? <LoadingState label="Loading events…" /> : error && !eventId ? <ErrorState message={error} /> : !eventId ? <EmptyState title="Choose an event">Select an event to view its registrations.</EmptyState> : loadingRows ? <LoadingState label="Loading attendees…" /> : error ? <ErrorState message={error} onRetry={() => load(page)} /> : payload?.results?.length ? <><div className="table-wrap"><table className="data-table"><thead><tr><th>Attendee</th><th>Event</th><th>Registered</th><th>Status</th><th>Updated</th></tr></thead><tbody>{payload.results.map((row) => <tr key={row.id}><td><strong>{[row.attendee.first_name, row.attendee.last_name].filter(Boolean).join(' ') || row.attendee.username}</strong><small>@{row.attendee.username}</small></td><td>{events.find((item) => item.id === row.event_id)?.title || `Event ${row.event_id}`}</td><td>{formatDate(row.registered_at)}</td><td><StatusPill>{row.status}</StatusPill></td><td>{row.status === 'cancelled' ? formatDate(row.updated_at) : '—'}</td></tr>)}</tbody></table></div><Pagination page={page} pages={Math.ceil(payload.count / 20)} onChange={load} /></> : !error && <EmptyState title="No registrations match">Try another status or check back when people register.</EmptyState>}</>;
}

