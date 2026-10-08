import api from './api';
import frontendPackage from '../../package.json';
import { getApiErrorMessage } from './api';
import { register, resendOtp, verifyEmail } from './authService';

test('auth service builds requests to the Django auth API', async () => {
  const post = jest.spyOn(api, 'post').mockResolvedValue({ status: 200 });
  const registration = { username: 'planner', email: 'planner@example.com' };

  await register(registration);
  await verifyEmail({ email: registration.email, otp: '123456' });
  await resendOtp({ email: registration.email });

  const [registerPath, verifyPath, resendPath] = post.mock.calls.map(([path]) => path);
  expect(registerPath).toBe('/api/auth/register/');
  expect(verifyPath).toBe('/api/auth/verify-email/');
  expect(resendPath).toBe('/api/auth/resend-otp/');
  expect(frontendPackage.proxy).toBe('http://localhost:8000');
  expect(new URL(registerPath, 'http://localhost:3000').pathname).toBe('/api/auth/register/');
  post.mockRestore();
});

test('shows the requested message when Axios has no response', () => {
  expect(getApiErrorMessage({ request: {} })).toBe(
    'Unable to connect to the server. Make sure Django is running.',
  );
});
