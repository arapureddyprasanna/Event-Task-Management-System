import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { getUserDashboard } from '../../api/dashboard';
import { listNotifications, markNotificationRead } from '../../api/notifications';
import { DashboardPage, NotificationsPage } from './UserPages';

jest.mock('../../api/dashboard', () => ({ getUserDashboard: jest.fn() }));
jest.mock('../../api/notifications', () => ({
  listNotifications: jest.fn(),
  markAllNotificationsRead: jest.fn(),
  markNotificationRead: jest.fn(),
}));

const dashboardData = {
  registrations: { total: 2, active: 1, upcoming: 1, cancelled: 1 },
  tasks: { total: 3, pending: 1, in_progress: 1, completed: 1, overdue: 1 },
  unread_notifications: 1,
  upcoming_events: [{
    id: 17,
    title: 'Neighborhood gathering',
    start_at: '2030-05-01T10:00:00Z',
    location: 'Central Hall',
    registration_count: 4,
    remaining_seats: 2,
    availability: 'available',
  }],
  recent_notifications: [],
  recent_activity: [],
};

beforeEach(() => jest.clearAllMocks());

test('dashboard renders real summary data from its API', async () => {
  getUserDashboard.mockResolvedValue({ data: dashboardData });

  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText('Neighborhood gathering')).toBeInTheDocument();
  expect(screen.getByText('Unread notifications')).toBeInTheDocument();
  expect(screen.getAllByText('1', { selector: 'strong' }).length).toBeGreaterThan(0);
  expect(getUserDashboard).toHaveBeenCalledTimes(1);
});

test('notification read action updates the API-backed entry', async () => {
  const unread = {
    id: 9,
    title: 'Event registration confirmed',
    message: 'You are registered for a gathering.',
    is_read: false,
    created_at: '2030-04-20T10:00:00Z',
  };
  listNotifications.mockResolvedValue({ data: { count: 1, results: [unread] } });
  markNotificationRead.mockResolvedValue({ data: { ...unread, is_read: true } });

  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><NotificationsPage /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Mark as read' }));

  await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith(9));
  expect(await screen.findByText('Notification marked as read.')).toBeInTheDocument();
  expect(screen.getByRole('article').querySelector('.status-pill')).toHaveTextContent('Read');
});
