import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getUserDashboard } from '../../api/dashboard';
import { listActivity } from '../../api/activity';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '../../api/notifications';
import { cancelRegistration, myRegistrations } from '../../api/registrations';
import { myTasks, updateTask } from '../../api/tasks';
import { getApiErrorMessage } from '../../api/client';
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, StatusPill } from '../../components/common/States';
import { formatDate } from '../../components/events/EventCard';
import toast from 'react-hot-toast';

export function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    setLoading(true); setError('');
    getUserDashboard().then(({ data }) => setSummary(data))
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  }, [reload]);

  return <><PageHeader eyebrow="Your space" title="A good day to make a plan.">Your gatherings and next steps, all in one place.</PageHeader>{loading ? <LoadingState label="Gathering your overview…" /> : error ? <ErrorState message={error} onRetry={() => setReload((value) => value + 1)} /> : summary && <><div className="stat-grid"><StatCard label="Registered events" value={summary.registrations.total} detail={`${summary.registrations.active} active · ${summary.registrations.cancelled} cancelled`} icon="✳" /><StatCard label="Upcoming registrations" value={summary.registrations.upcoming} detail="Events you’re registered for" icon="↗" /><StatCard label="Assigned tasks" value={summary.tasks.total} detail={`${summary.tasks.pending} pending · ${summary.tasks.in_progress} in progress`} icon="✓" /><StatCard label="Completed tasks" value={summary.tasks.completed} detail="Tasks you’ve finished" icon="○" /><StatCard label="Overdue tasks" value={summary.tasks.overdue} detail="Need your attention" icon="!" /><StatCard label="Unread notifications" value={summary.unread_notifications} detail="Updates for you" icon="◌" /></div><section className="dashboard-welcome"><div><p className="eyebrow">A little inspiration</p><h2>Good plans make room<br />for <em>good memories.</em></h2><p>Your events and next steps, all in one place.</p><div className="button-row"><Link to="/events" className="button button-dark">Explore events <span aria-hidden="true">↗</span></Link><Link to="/my/tasks" className="text-link">See my tasks</Link></div></div><div className="welcome-art" aria-hidden="true"><span className="welcome-sun" /><span className="welcome-ring" /><span className="welcome-plant">✳</span></div></section><div className="dashboard-lower"><section className="surface-card"><div className="surface-heading"><div><p className="eyebrow">Coming up</p><h2>Upcoming events</h2></div><Link className="arrow-link" to="/events">Browse <span aria-hidden="true">↗</span></Link></div>{summary.upcoming_events.length ? <div className="dashboard-item-list">{summary.upcoming_events.map((event) => <Link to={`/events/${event.id}`} key={event.id}><strong>{event.title}</strong><span>{formatDate(event.start_at)} · {event.location}</span><small>{event.availability === 'available' ? `${event.registration_count} registered${event.remaining_seats == null ? '' : ` · ${event.remaining_seats} seats left`}` : event.availability.replaceAll('_', ' ')}</small></Link>)}</div> : <EmptyState title="No upcoming events">The calendar is quiet for now.</EmptyState>}</section><section className="surface-card"><div className="surface-heading"><div><p className="eyebrow">Latest updates</p><h2>Recent notifications</h2></div><Link className="arrow-link" to="/notifications">See all</Link></div>{summary.recent_notifications.length ? summary.recent_notifications.map((notice) => <article className="dashboard-feed-item" key={notice.id}><strong>{notice.title}</strong><p>{notice.message}</p><small>{formatDate(notice.created_at)}</small></article>) : <EmptyState title="You’re all caught up">New updates will appear here.</EmptyState>}<div className="surface-heading"><h2>Recent activity</h2><Link className="arrow-link" to="/history">See history</Link></div>{summary.recent_activity.length ? summary.recent_activity.map((activity) => <article className="dashboard-feed-item" key={activity.id}><strong>{activity.description}</strong><small>{formatDate(activity.created_at)}</small></article>) : <EmptyState title="No recent activity">Your recent event and task activity will appear here.</EmptyState>}</section></div></>}</>;
}

function StatCard({ label, value, detail, icon }) {
  return <article className="stat-card"><span className="stat-icon" aria-hidden="true">{icon}</span><span className="stat-label">{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

export function MyRegistrationsPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const load = (nextPage = page, nextStatus = status) => {
    setLoading(true); setError('');
    myRegistrations({ page: nextPage, page_size: 10, status: nextStatus || undefined })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  const cancel = async (registration) => {
    if (!window.confirm(`Cancel your registration for “${registration.event.title}”?`)) return;
    setBusyId(registration.id);
    try {
      const { data } = await cancelRegistration(registration.event.id);
      setPayload((current) => ({
        ...current,
        results: current.results.map((item) => item.id === data.id ? { ...item, ...data } : item),
      }));
      toast.success(`Registration for “${registration.event.title}” cancelled.`);
    } catch (requestError) { toast.error(getApiErrorMessage(requestError)); }
    finally { setBusyId(null); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1, status);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  return <><PageHeader eyebrow="Your calendar" title="My registrations.">The gatherings you’ve chosen to be part of.</PageHeader><div className="filter-bar"><label className="select-control"><span>Registration status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All registrations</option><option value="registered">Registered</option><option value="cancelled">Cancelled</option></select></label></div>{error && <div className="inline-alert" role="alert">{error}</div>}{loading ? <LoadingState label="Loading registrations…" /> : payload?.results?.length ? <><div className="registration-list">{payload.results.map((registration) => <article className="registration-card" key={registration.id}><div className="registration-date"><strong>{new Date(registration.event.start_at).toLocaleDateString(undefined, { day: '2-digit' })}</strong><span>{new Date(registration.event.start_at).toLocaleDateString(undefined, { month: 'short' })}</span></div><div className="registration-main"><h2><Link to={`/events/${registration.event.id}`}>{registration.event.title}</Link></h2><p>{registration.event.location} <span>·</span> {formatDate(registration.event.start_at)}</p><small>Registered {formatDate(registration.registered_at)}</small>{registration.status === 'cancelled' && <small>Updated {formatDate(registration.updated_at)}</small>}</div><div className="registration-side"><StatusPill>{registration.status}</StatusPill><StatusPill tone={`event-${registration.event.status}`}>{registration.event.status}</StatusPill><Link className="arrow-link" to={`/events/${registration.event.id}`}>Details <span aria-hidden="true">↗</span></Link>{registration.status === 'registered' && <button className="button button-danger button-small" type="button" disabled={busyId === registration.id} onClick={() => cancel(registration)}>{busyId === registration.id ? 'Cancelling…' : 'Cancel registration'}</button>}</div></article>)}</div><Pagination page={page} pages={Math.ceil(payload.count / 10)} onChange={load} /></> : error ? null : <EmptyState title="Your calendar starts here">Explore the events calendar and register for something that catches your eye.<p><Link className="text-link" to="/events">Explore events</Link></p></EmptyState>}</>;
}

export function MyTasksPage() {
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const load = (nextPage = page, nextStatus = status, nextPriority = priority) => {
    setLoading(true); setError('');
    myTasks({ page: nextPage, page_size: 10, status: nextStatus || undefined, priority: nextPriority || undefined })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1, status, priority);
  }, [status, priority]); // eslint-disable-line react-hooks/exhaustive-deps
  const progress = async (task, nextStatus) => {
    setBusyId(task.id);
    try { 
      await updateTask(task.id, { status: nextStatus }); 
      toast.success('Task updated successfully.');
      load(page); 
    }
    catch (requestError) { toast.error(getApiErrorMessage(requestError)); }
    finally { setBusyId(null); }
  };
  return <><PageHeader eyebrow="Your next steps" title="My tasks.">Small steps add up to a gathering everyone can enjoy.</PageHeader><div className="filter-bar"><label className="select-control"><span>Task status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="todo">To do</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label><label className="select-control"><span>Priority</span><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">All priorities</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select></label></div>{error && <div className="inline-alert" role="alert">{error}</div>}{loading ? <LoadingState label="Loading your tasks…" /> : payload?.results?.length ? <><div className="task-list">{payload.results.map((task) => <article className="task-card" key={task.id}><div className={`task-check task-${task.status}`} aria-hidden="true">{task.status === 'completed' ? '✓' : '·'}</div><div className="task-content"><div className="task-card-heading"><h2>{task.title}</h2><StatusPill>{task.status}</StatusPill></div><p>{task.description}</p><div className="task-meta"><Link to={`/events/${task.event}`}>{task.event_title}</Link><StatusPill tone={`priority-${task.priority}`}>{task.priority}</StatusPill>{task.due_at && <span className={task.is_overdue ? 'overdue-label' : ''}>{task.is_overdue ? 'Overdue · ' : 'Due '}{formatDate(task.due_at)}</span>}</div></div><div className="task-actions">{task.status === 'todo' && <button className="button button-quiet" type="button" disabled={busyId === task.id} onClick={() => progress(task, 'in_progress')}>{busyId === task.id ? 'Saving…' : 'Start task'}</button>}{task.status === 'in_progress' && <button className="button button-dark button-small" type="button" disabled={busyId === task.id} onClick={() => progress(task, 'completed')}>{busyId === task.id ? 'Saving…' : 'Mark complete'}</button>}</div></article>)}</div><Pagination page={page} pages={Math.ceil(payload.count / 10)} onChange={load} /></> : !error && <EmptyState title="No tasks on your list">When an organizer assigns you a task, it will show up here.</EmptyState>}</>;
}

export function NotificationsPage() {
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const load = (nextPage = page, nextFilter = filter) => {
    setLoading(true); setError('');
    listNotifications({ page: nextPage, page_size: 20, unread: nextFilter || undefined })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1, filter); }, [filter, reload]);
  const markRead = async (notification) => {
    setBusyId(notification.id);
    try {
      const { data } = await markNotificationRead(notification.id);
      window.dispatchEvent(new Event('gather:notifications-changed'));
      if (filter === 'true') load(page);
      else setPayload((current) => ({ ...current, results: current.results.map((item) => item.id === data.id ? data : item) }));
      toast.success('Notification marked as read.');
    } catch (requestError) { toast.error(getApiErrorMessage(requestError)); }
    finally { setBusyId(null); }
  };
  const markAllRead = async () => {
    try {
      await markAllNotificationsRead();
      window.dispatchEvent(new Event('gather:notifications-changed'));
      setPayload((current) => current ? { ...current, results: current.results.map((item) => ({ ...item, is_read: true })) } : current);
      toast.success('All notifications marked as read.');
      if (filter === 'true') setReload((value) => value + 1);
    } catch (requestError) { toast.error(getApiErrorMessage(requestError)); }
  };
  return <><PageHeader eyebrow="Stay in the loop" title="Notifications.">Updates about your events, registrations, and tasks.</PageHeader><div className="filter-bar"><label className="select-control"><span>Show</span><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">All notifications</option><option value="true">Unread</option><option value="false">Read</option></select></label><button className="button button-quiet" type="button" onClick={markAllRead}>Mark all as read</button></div>{loading ? <LoadingState label="Loading notifications…" /> : error && !payload ? <ErrorState message={error} onRetry={() => setReload((value) => value + 1)} /> : error ? <><div className="inline-alert" role="alert">{error}</div><button className="button button-quiet" type="button" onClick={() => load(page)}>Try again</button></> : payload?.results?.length ? <><div className="notification-list">{payload.results.map((item) => <article className={`notification-card${item.is_read ? ' notification-read' : ' notification-unread'}`} key={item.id}><div className="notification-copy"><div className="notification-card-heading"><h2>{item.title}</h2><StatusPill tone={item.is_read ? 'inactive' : 'active'}>{item.is_read ? 'Read' : 'Unread'}</StatusPill></div><p>{item.message}</p><small>{formatDate(item.created_at)}</small></div>{!item.is_read && <button className="button button-quiet button-small" type="button" disabled={busyId === item.id} onClick={() => markRead(item)}>{busyId === item.id ? 'Saving…' : 'Mark as read'}</button>}</article>)}</div><Pagination page={page} pages={Math.ceil(payload.count / 20)} onChange={load} /></> : <EmptyState title={filter === 'true' ? 'You’re all caught up' : 'No notifications yet'}>Event and task updates will appear here.</EmptyState>}</>;
}

export function HistoryPage() {
  const [payload, setPayload] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const load = (nextPage = page) => {
    setLoading(true); setError('');
    listActivity({ page: nextPage, page_size: 20 })
      .then(({ data }) => { setPayload(data); setPage(nextPage); })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(1); }, [reload]);
  return <><PageHeader eyebrow="The story so far" title="Activity history.">A chronological record of event and task changes.</PageHeader>{loading ? <LoadingState label="Loading activity…" /> : error ? <ErrorState message={error} onRetry={() => setReload((value) => value + 1)} /> : payload?.results?.length ? <><div className="activity-list">{payload.results.map((item) => <article className="activity-card" key={item.id}><div className="activity-marker" aria-hidden="true">✳</div><div><h2>{item.description}</h2><p>{item.action_type.replaceAll('_', ' ')}</p>{item.target_event && <Link to={`/events/${item.target_event.id}`}>Event: {item.target_event.title}</Link>}{item.target_task && <p>Task: {item.target_task.title}</p>}{item.target_user && <p>Member: {item.target_user.first_name || item.target_user.username}</p>}<small>{formatDate(item.created_at)}</small></div></article>)}</div><Pagination page={page} pages={Math.ceil(payload.count / 20)} onChange={load} /></> : <EmptyState title="No activity yet">Relevant event and task activity will appear here.</EmptyState>}</>;
}
