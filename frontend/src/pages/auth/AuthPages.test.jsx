import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from './AuthPages';
import { useAuth } from '../../context/AuthContext';

jest.mock('../../context/AuthContext', () => ({ useAuth: jest.fn() }));

test('login explains invalid credentials and clears the password after failure', async () => {
  const signIn = jest.fn().mockRejectedValue({ response: { status: 401, data: { detail: 'Invalid username/email or password.' } } });
  useAuth.mockReturnValue({ signIn });
  render(<MemoryRouter><LoginPage /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: 'person@example.com' } });
  const password = screen.getByLabelText(/^password$/i);
  fireEvent.change(password, { target: { value: 'incorrect-secret' } });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/username\/email or password is incorrect/i);
  await waitFor(() => expect(password).toHaveValue(''));
  expect(screen.getByLabelText(/username or email/i)).toHaveValue('person@example.com');
});

test('login presents verification and approval failures clearly', async () => {
  const signIn = jest.fn().mockRejectedValue({ response: { status: 403, data: { code: 'email_not_verified' } } });
  useAuth.mockReturnValue({ signIn });
  render(<MemoryRouter><LoginPage /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText(/username or email/i), { target: { value: 'person' } });
  fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/verify your email/i);
});
