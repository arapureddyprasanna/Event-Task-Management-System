import { useEffect, useState } from 'react';
import { eventRegistrations } from '../../api/registrations';
import { listEvents } from '../../api/events';
import { createEventTask, eventTasks, updateTask } from '../../api/tasks';
import { getApiErrorMessage } from '../../api/client';
import { EmptyState, LoadingState, PageHeader, Pagination, StatusPill } from '../../components/common/States';
import { formatDate } from '../../components/events/EventCard';
import { Field } from './TaskForms';

const nextStatuses = {
  todo: ['in_progress', 'cancelled'],
  in_progress: ['todo', 'completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

function AdminTaskManager() {
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState('');
  const [attendees, setAttendees] = useState([]);
  const [attendeePage, setAttendeePage] = useState(1);
  const [hasMoreAttendees, setHasMoreAttendees] = useState(false);
  const [loadingAttendees, setLoadingAttendees] = useState(false);
  const [tasks, setTasks] = useState(null);
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [search, setSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [taskPriority, setTaskPriority] = useState('medium');
  const [assigneeId, setAssigneeId] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [editingTask, setEditingTask] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listEvents({ page_size: 100 }).then(({ data }) => setEvents(data.results || []))
      .catch((e) => setError(getApiErrorMessage(e))).finally(() => setLoading(false));
  }, []);

  const loadTasks = (nextPage = page, nextStatus = status, nextPriority = priority, nextSearch = submittedSearch) => {
    if (!eventId) return;
    setLoading(true);
    setError('');
    eventTasks(eventId, { page: nextPage, page_size: 20, status: nextStatus || undefined, priority: nextPriority || undefined, search: nextSearch || undefined })
      .then(({ data }) => { setTasks(data); setPage(nextPage); })
      .catch((e) => setError(getApiErrorMessage(e))).finally(() => setLoading(false));
  };

  const loadAttendees = async (nextPage = 1, append = false) => {
    if (!eventId) return;
    setLoadingAttendees(true);
    try {
      const { data } = await eventRegistrations(eventId, { page: nextPage, page_size: 100, status: 'registered' });
      setAttendees((current) => append ? [...current, ...(data.results || [])] : (data.results || []));
      setAttendeePage(nextPage);
      setHasMoreAttendees(Boolean(data.next));
    } catch (requestError) { setError(getApiErrorMessage(requestError)); }
    finally { setLoadingAttendees(false); }
  };

  // Reload task rows and active attendees when the event or filters change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!eventId) { setTasks(null); setAttendees([]); setHasMoreAttendees(false); return; }
    loadTasks(1, status, priority);
    loadAttendees(1);
  }, [eventId, status, priority, submittedSearch]); // eslint-disable-line react-hooks/exhaustive-deps

  const createTask = async (event) => {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    const values = { title: title.trim(), description: description.trim(), priority: taskPriority };
    if (assigneeId) values.assignee_id = Number(assigneeId);
    if (dueAt) values.due_at = new Date(dueAt).toISOString();
    try {
      await createEventTask(eventId, values);
      setTitle(''); setDescription(''); setAssigneeId(''); setDueAt('');
      setNotice('Task created.');
      loadTasks(1);
    } catch (requestError) { setError(getApiErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const patchTask = async (task, values) => {
    setError(''); setNotice('');
    try {
      await updateTask(task.id, values);
      setNotice('Task updated.');
      loadTasks(page);
      setEditingTask(null);
      return '';
    } catch (requestError) {
      const message = getApiErrorMessage(requestError);
      setError(message);
      return message;
    }
  };

  return (
    <>
      <PageHeader eyebrow="Task coordination" title="Keep the details moving.">Create tasks for an event, assign registered attendees, and update the work as it moves.</PageHeader>
      {notice && <div className="inline-success" role="status">{notice}</div>}
      <div className="filter-bar">
        <label className="select-control"><span>Event</span><select value={eventId} onChange={(e) => setEventId(e.target.value)}><option value="">Choose an event</option>{events.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}</select></label>
        <label className="select-control"><span>Task status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{['todo', 'in_progress', 'completed', 'cancelled'].map((item) => <option value={item} key={item}>{item.replaceAll('_', ' ')}</option>)}</select></label>
        <label className="select-control"><span>Priority</span><select value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">All priorities</option>{['low', 'medium', 'high', 'urgent'].map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <form className="inline-search" onSubmit={(e) => { e.preventDefault(); setSubmittedSearch(search); }}><label className="search-control"><span aria-hidden="true">⌕</span><span className="sr-only">Search tasks</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tasks" /></label><button className="button button-quiet" type="submit">Search</button></form>
      </div>
      {error && <div className="inline-alert" role="alert">{error}</div>}
      {loading && !events.length ? <LoadingState label="Loading events…" /> : !eventId ? <EmptyState title="Choose an event">Tasks are organized within an event. Select one to view or create tasks.</EmptyState> : (
        <>
          <form className="editor-card task-create-form" onSubmit={createTask}>
            <div className="surface-heading"><div><p className="eyebrow">New task</p><h2>Add a next step</h2></div></div>
            <div className="form-grid">
              <Field label="Task title"><input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required /></Field>
              <Field label="Priority"><select value={taskPriority} onChange={(e) => setTaskPriority(e.target.value)}>{['low', 'medium', 'high', 'urgent'].map((item) => <option value={item} key={item}>{item}</option>)}</select></Field>
              <Field label="Assign to"><select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}><option value="">Leave unassigned</option>{attendees.map((row) => <option key={row.attendee.id} value={row.attendee.id}>{[row.attendee.first_name, row.attendee.last_name].filter(Boolean).join(' ') || row.attendee.username}</option>)}</select></Field>
              <Field label="Due date"><input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} /></Field>
              <Field label="Description" full><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} required /></Field>
            </div>
            <div className="form-actions"><button className="button button-dark" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create task'}</button><span className="muted-note">Assignees must be active event registrants.</span>{hasMoreAttendees && <button className="button button-quiet button-small" type="button" disabled={loadingAttendees} onClick={() => loadAttendees(attendeePage + 1, true)}>{loadingAttendees ? 'Loading attendees…' : 'Load more attendees'}</button>}</div>
          </form>
          {loading ? <LoadingState label="Loading tasks…" /> : tasks?.results?.length ? <>
            <div className="admin-task-list">{tasks.results.map((task) => <article className="admin-task-row" key={task.id}>
              <div className="admin-task-main"><div className="task-card-heading"><h2>{task.title}</h2><StatusPill>{task.status}</StatusPill><StatusPill tone={`priority-${task.priority}`}>{task.priority}</StatusPill></div><p>{task.description}</p><div className="task-meta"><span>{task.assignee ? `Assigned to ${[task.assignee.first_name, task.assignee.last_name].filter(Boolean).join(' ') || task.assignee.username}` : 'Unassigned'}</span>{task.due_at && <span className={task.is_overdue ? 'overdue-label' : ''}>{task.is_overdue ? 'Overdue · ' : 'Due '}{formatDate(task.due_at)}</span>}</div></div>
              <div className="admin-task-edit"><label><span className="sr-only">Assignee</span><select aria-label={`Assignee for ${task.title}`} value={task.assignee?.id || ''} onChange={(e) => patchTask(task, { assignee_id: e.target.value ? Number(e.target.value) : null })}><option value="">Unassigned</option>{attendees.map((row) => <option key={row.attendee.id} value={row.attendee.id}>{row.attendee.username}</option>)}</select></label><label><span className="sr-only">Status</span><select aria-label={`Status for ${task.title}`} value={task.status} onChange={(e) => patchTask(task, { status: e.target.value })}><option value={task.status}>{task.status.replaceAll('_', ' ')}</option>{(nextStatuses[task.status] || []).map((value) => <option value={value} key={value}>{value.replaceAll('_', ' ')}</option>)}</select></label><button className="button button-quiet button-small" type="button" onClick={() => setEditingTask(task)}>Edit details</button></div>
            </article>)}</div>
            <Pagination page={page} pages={Math.ceil(tasks.count / 20)} onChange={loadTasks} />
          </> : <EmptyState title="No tasks for this event">Add the first task above, or adjust your filters.</EmptyState>}
        </>
      )}
      {editingTask && <TaskEditModal task={editingTask} attendees={attendees} onSave={(values) => patchTask(editingTask, values)} onClose={() => setEditingTask(null)} />}
    </>
  );
}

function TaskEditModal({ task, attendees, onSave, onClose }) {
  const toInput = (value) => value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);
  const [priority, setPriority] = useState(task.priority);
  const [status, setStatus] = useState(task.status);
  const [assigneeId, setAssigneeId] = useState(task.assignee?.id || '');
  const [dueAt, setDueAt] = useState(toInput(task.due_at));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    const values = { title: title.trim(), description: description.trim(), priority, status, assignee_id: assigneeId ? Number(assigneeId) : null, due_at: dueAt ? new Date(dueAt).toISOString() : null };
    try {
      const saveError = await onSave(values);
      if (saveError) setError(saveError);
    }
    catch (requestError) { setError(getApiErrorMessage(requestError)); }
    finally { setSaving(false); }
  };
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><form className="modal-card task-edit-modal" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="edit-task-title"><button className="modal-close" type="button" aria-label="Close" onClick={onClose}>×</button><p className="eyebrow">Task details</p><h2 id="edit-task-title">Edit task</h2><div className="form-grid"><Field label="Title"><input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required /></Field><Field label="Priority"><select value={priority} onChange={(e) => setPriority(e.target.value)}>{['low', 'medium', 'high', 'urgent'].map((item) => <option value={item} key={item}>{item}</option>)}</select></Field><Field label="Status"><select value={status} onChange={(e) => setStatus(e.target.value)}>{[task.status, ...(nextStatuses[task.status] || [])].map((item) => <option value={item} key={item}>{item.replaceAll('_', ' ')}</option>)}</select></Field><Field label="Assignee"><select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}><option value="">Unassigned</option>{attendees.map((row) => <option key={row.attendee.id} value={row.attendee.id}>{row.attendee.username}</option>)}</select></Field><Field label="Due date"><input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} /></Field><Field label="Description" full><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} required /></Field></div>{error && <div className="inline-alert" role="alert">{error}</div>}<div className="form-actions"><button className="button button-dark" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save task'}</button><button className="button button-quiet" type="button" onClick={onClose}>Cancel</button></div></form></div>;
}

export default AdminTaskManager;
