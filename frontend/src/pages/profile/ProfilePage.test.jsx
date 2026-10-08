import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProfilePage from './ProfilePage';
import { useAuth } from '../../context/AuthContext';

jest.mock('../../context/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('../../api/auth', () => ({ changePassword: jest.fn(), updateProfile: jest.fn() }));

function mount() {
  return render(<MemoryRouter initialEntries={['/profile']}><Routes>
    <Route path="/profile" element={<ProfilePage />} />
    <Route path="/login" element={<div>Login destination</div>} />
  </Routes></MemoryRouter>);
}

beforeEach(() => useAuth.mockReturnValue({
  user: { username: 'member', email: 'member@example.com', first_name: 'Member', is_email_verified: true },
  refreshProfile: jest.fn(), signOut: jest.fn().mockResolvedValue(),
}));

test('cancelled profile logout leaves the account signed in', async () => {
  const originalConfirm = window.confirm;
  window.confirm = jest.fn().mockReturnValue(false);
  mount();
  fireEvent.click(screen.getByRole('button', { name: /logout/i }));
  expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to log out?');
  expect(useAuth.mock.results[0].value.signOut).not.toHaveBeenCalled();
  expect(screen.getByText('Your profile.')).toBeInTheDocument();
  window.confirm = originalConfirm;
});

test('confirmed profile logout clears auth and navigates to login', async () => {
  const originalConfirm = window.confirm;
  window.confirm = jest.fn().mockReturnValue(true);
  mount();
  fireEvent.click(screen.getByRole('button', { name: /logout/i }));
  expect(await screen.findByText('Login destination')).toBeInTheDocument();
  expect(useAuth.mock.results[0].value.signOut).toHaveBeenCalledTimes(1);
  window.confirm = originalConfirm;
});
