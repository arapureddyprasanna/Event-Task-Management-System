import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';
import { register } from './services/authService';

jest.mock('./services/authService', () => ({
  register: jest.fn(),
  verifyEmail: jest.fn(),
  resendOtp: jest.fn(),
}));

const goodPassword = 'BetterRiver2026!';

function renderRegistration() {
  window.history.pushState({}, '', '/register');
  return render(<App />);
}

function fillRequiredFields({ email = 'person@example.com', password = goodPassword, confirmation = password, username = 'planner-person' } = {}) {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: username } });
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password', { selector: 'input' }), { target: { value: password } });
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: confirmation } });
}

beforeEach(() => {
  jest.clearAllMocks();
  register.mockResolvedValue({ status: 201, data: { detail: 'Registration successful.' } });
});

test('renders the registration form', () => {
  renderRegistration();
  expect(screen.getByRole('heading', { name: /create your account/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
});

test('redirects an unauthenticated visitor from the workspace to sign in', async () => {
  window.history.pushState({}, '', '/dashboard');

  render(<App />);

  expect(await screen.findByRole('heading', { name: /sign in to gather/i })).toBeInTheDocument();
});

test.each([
  ['', 'Please enter your email address.'],
  ['not-an-email', 'Please enter a valid email address.'],
])('rejects invalid or empty email %p before sending a request', (email, message) => {
  renderRegistration();
  fillRequiredFields({ email });

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  expect(screen.getByText(message)).toBeInTheDocument();
  expect(register).not.toHaveBeenCalled();
});

test('shows live password rules that match Django configuration', () => {
  renderRegistration();
  const password = screen.getByLabelText('Password', { selector: 'input' });
  const requirements = screen.getByRole('list', { name: /password requirements/i });

  fireEvent.change(password, { target: { value: '1234567' } });
  expect(requirements.querySelector('li').className).not.toContain('passed');
  fireEvent.change(password, { target: { value: '12345678' } });
  expect(requirements.querySelector('li').className).toContain('passed');
  expect(screen.getByText(/uppercase letter/i).closest('li').className).not.toContain('passed');
  fireEvent.change(password, { target: { value: goodPassword } });
  for (const rule of ['8 characters', 'uppercase letter', 'lowercase letter', 'number', 'special character']) {
    expect(screen.getByText(new RegExp(rule, 'i')).closest('li').className).toContain('passed');
  }
  expect(screen.getByText(/password and confirmation match/i).closest('li').className).not.toContain('passed');
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: goodPassword } });
  expect(screen.getByText(/password and confirmation match/i).closest('li').className).toContain('passed');
});

test('shows a confirm-password mismatch and does not submit', () => {
  renderRegistration();
  fillRequiredFields({ confirmation: 'DifferentPassword4!' });

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
  expect(screen.getByText(/password and confirmation match/i).closest('li').className).not.toContain('passed');
  expect(register).not.toHaveBeenCalled();
});

test('shows backend duplicate-email error beside the email field', async () => {
  register.mockRejectedValueOnce({ response: { status: 400, data: { email: ['A user with this email already exists.'] } } });
  renderRegistration();
  fillRequiredFields();

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  expect(await screen.findByText('A user with this email already exists.')).toBeInTheDocument();
  expect(screen.getByLabelText('Email address')).toHaveAttribute('aria-invalid', 'true');
  expect(screen.queryByText('Please check your information and try again.')).not.toBeInTheDocument();
});

test('shows backend password-validator errors beside the password field', async () => {
  register.mockRejectedValueOnce({ response: { status: 400, data: { password: ['This password is too common.'] } } });
  renderRegistration();
  fillRequiredFields();

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  expect(await screen.findByText('This password is too common.')).toBeInTheDocument();
  expect(screen.getByLabelText('Password', { selector: 'input' })).toHaveAttribute('aria-invalid', 'true');
});

test('shows backend duplicate-username error beside the username field', async () => {
  register.mockRejectedValueOnce({ response: { status: 400, data: { username: ['This username is already registered.'] } } });
  renderRegistration();
  fillRequiredFields();

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  expect(await screen.findByText('This username is already registered.')).toBeInTheDocument();
  expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true');
});

test('successful registration redirects directly to login', async () => {
  renderRegistration();
  fillRequiredFields({ email: '  Person@Example.com  ' });

  fireEvent.click(screen.getByRole('button', { name: /create account/i }));

  await waitFor(() => expect(register).toHaveBeenCalledWith(expect.objectContaining({ email: 'person@example.com' })));
  expect(await screen.findByRole('heading', { name: /sign in to gather/i })).toBeInTheDocument();
  expect(screen.getByText('Account created. Sign in to continue.')).toBeInTheDocument();
});
