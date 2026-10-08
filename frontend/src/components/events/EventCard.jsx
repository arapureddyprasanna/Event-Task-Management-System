import { Link } from 'react-router-dom';
import { StatusPill } from '../common/States';

export function formatDate(value, options = { dateStyle: 'medium', timeStyle: 'short' }) {
  if (!value) return 'Date to be announced';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date to be announced' : new Intl.DateTimeFormat(undefined, options).format(date);
}

function EventCard({ event }) {
  return (
    <article className="event-card">
      <div className="event-card-art"><span className="event-art-stamp">GATHER<br />TOGETHER</span><span className="event-art-date">{new Date(event.start_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span></div>
      <div className="event-card-body">
        <div className="event-card-meta"><span>{event.location}</span><StatusPill>{event.availability || event.status}</StatusPill></div>
        <h3><Link to={`/events/${event.id}`}>{event.title}</Link></h3>
        <p>{event.description}</p>
        <div className="event-card-footer"><span>{formatDate(event.start_at)} · {event.registration_count ?? 0} registered{event.remaining_seats == null ? '' : ` · ${event.remaining_seats} seats left`}</span><Link className="arrow-link" to={`/events/${event.id}`}>Explore <span aria-hidden="true">↗</span></Link></div>
      </div>
    </article>
  );
}

export default EventCard;
