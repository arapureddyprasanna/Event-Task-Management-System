import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../../App';
import { getProfile } from '../../api/auth';
import { getEvent } from '../../api/events';
import { myRegistrations, registerForEvent } from '../../api/registrations';
import { sessionKeys } from '../../api/client';

jest.mock('../../api/auth', () => ({
  ...jest.requireActual('../../api/auth'),
  getProfile: jest.fn(),
}));
jest.mock('../../api/events', () => ({
  getEvent: jest.fn(),
  listEvents: jest.fn(),
  createEvent: jest.fn(),
  updateEvent: jest.fn(),
}));
jest.mock('../../api/registrations', () => ({
  myRegistrations: jest.fn(),
  eventRegistrations: jest.fn(),
  registerForEvent: jest.fn(),
  cancelRegistration: jest.fn(),
}));

const event = {
  id: 42,
  title: 'Community picnic',
  description: 'A day outdoors.',
  location: 'Central Park',
  start_at: '2030-05-01T10:00:00Z',
  end_at: '2030-05-01T12:00:00Z',
  status: 'published',
  availability: 'available',
  registration_count: 0,
  remaining_seats: 10,
  capacity: 10,
  organizer: { username: 'organizer', first_name: 'Event', last_name: 'Host' },
};

function openEventDetails() {
  window.history.pushState({}, '', '/events/42');
  return render(<App />);
}

beforeEach(() => {
  window.sessionStorage.clear();
  jest.clearAllMocks();
  getEvent.mockResolvedValue({ data: event });
  myRegistrations.mockResolvedValue({ data: { results: [], next: null } });
  registerForEvent.mockResolvedValue({
    data: { id: 5, status: 'registered', event },
  });
});

test('anonymous visitor is redirected to sign in without sending a registration request', async () => {
  openEventDetails();

  fireEvent.click(await screen.findByRole('button', { name: 'Register for event' }));

  expect(await screen.findByRole('heading', { name: 'Sign in to Gather' })).toBeInTheDocument();
  expect(window.location.pathname).toBe('/login');
  expect(registerForEvent).not.toHaveBeenCalled();
});

test.each([
  ['member', false],
  ['admin', true],
])('%s with a restored session can explicitly register using that account', async (username, isStaff) => {
  window.sessionStorage.setItem(sessionKeys.access, 'access-token');
  window.sessionStorage.setItem(sessionKeys.refresh, 'refresh-token');
  getProfile.mockResolvedValue({
    data: {
      username,
      is_staff: isStaff,
      is_superuser: false,
      is_email_verified: true,
      registration_demo_access: false,
    },
  });

  openEventDetails();

  expect(await screen.findByText((_, element) => (
    element.tagName === 'P'
    && element.textContent.includes(`You’re signed in as ${username}; registration will use this account.`)
  ))).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Register for event' }));

  await waitFor(() => expect(registerForEvent).toHaveBeenCalledWith('42'));
  expect(await screen.findByRole('status')).toHaveTextContent('You’re registered. We’ll see you there.');
});
