import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AppLayout from './AppLayout';
import { useAuth } from '../../context/AuthContext';
import { listNotifications } from '../../api/notifications';

jest.mock('../../context/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('../../api/notifications', () => ({ listNotifications: jest.fn() }));

function mount() {
  return render(<MemoryRouter><AppLayout /></MemoryRouter>);
}

beforeEach(() => {
  useAuth.mockReturnValue({ user: { username: 'member' }, isSuperuser: false, signOut: jest.fn() });
  listNotifications.mockResolvedValue({ data: { count: 3, results: [] } });
});

test('shows API-backed unread count and refreshes it after notification changes', async () => {
  mount();
  expect(await screen.findByText('3')).toBeInTheDocument();
  expect(listNotifications).toHaveBeenCalledWith({ unread: 'true', page_size: 1 });
  listNotifications.mockResolvedValueOnce({ data: { count: 0, results: [] } });
  window.dispatchEvent(new Event('gather:notifications-changed'));
  await waitFor(() => expect(screen.queryByLabelText(/unread notifications/i)).not.toBeInTheDocument());
});

test('hides a zero unread count and confirms sidebar logout', async () => {
  listNotifications.mockResolvedValue({ data: { count: 0, results: [] } });
  mount();
  await waitFor(() => expect(listNotifications).toHaveBeenCalled());
  expect(screen.queryByLabelText(/unread notifications/i)).not.toBeInTheDocument();
  window.confirm = jest.fn().mockReturnValue(false);
  fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
  expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to log out?');
  expect(useAuth.mock.results[0].value.signOut).not.toHaveBeenCalled();
});
