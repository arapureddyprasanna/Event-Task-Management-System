import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { forgotPassword, resetPassword } from '../../api/auth';
import { getApiErrorMessage } from '../../api/client';
import AuthLayout from '../../components/AuthLayout';
import FormMessage from '../../components/FormMessage';
import { useAuth } from '../../context/AuthContext';
import toast from 'react-hot-toast';
export function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn } = useAuth();
  const notice = location.state?.notice || '';

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);

    try {
      const user = await signIn({
        identifier: identifier.trim(),
        password,
      });

      const home = user.is_staff ? '/admin' : '/dashboard';
      const requested = location.state?.from;
      const requestedAdminPath = requested?.startsWith('/admin');
      const canReturnToRequestedPath =
        requested?.startsWith('/') &&
        Boolean(requestedAdminPath) === Boolean(user.is_staff);

      navigate(canReturnToRequestedPath ? requested : home, {
        replace: true,
      });
    } catch (requestError) {
      setPassword('');

      const code = requestError.response?.data?.code;
      const status = requestError.response?.status;
      const detail = requestError.response?.data?.detail;

      if (code === 'email_not_verified') {
        toast.error('Verify your email before signing in.');
      } else if (code === 'admin_request_pending') {
        toast.error('Your admin access request is awaiting approval.');
      } else if (code === 'admin_request_rejected') {
        toast.error('Your admin access request was not approved.');
      } else if (status === 401) {
        toast.error(
          'The username/email or password is incorrect. Check your details and try again.'
        );
      } else if (status === 403 && /verification/i.test(detail || '')) {
        toast.error('Verify your email before signing in.');
      } else if (status === 403 && /pending/i.test(detail || '')) {
        toast.error('Your admin access request is awaiting approval.');
      } else if (status === 403 && /rejected/i.test(detail || '')) {
        toast.error('Your admin access request was not approved.');
      } else if (!requestError.response) {
        toast.error(
          'Unable to connect to the server. Check your connection and try again.'
        );
      } else if (status >= 500) {
        toast.error(
          'The sign-in service is temporarily unavailable. Please try again shortly.'
        );
      } else {
        toast.error(
          'We couldn’t sign you in. Check your details and try again.'
        );
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      pageLabel="Good to have you back"
      title="Pick up where"
      titleAccent="you left off."
      description="Your events, people, and the next small step are all right here."
    >
      <p className="card-kicker">Welcome back</p>
      <h2>Sign in to Gather</h2>
      <p className="card-description">Use your username or email address.</p>

      <FormMessage tone="success">{notice}</FormMessage>

      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="identifier">Username or email</label>
          <input
            id="identifier"
            autoComplete="username"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="login-password">Password</label>

          <div className="password-field">
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
          </div>
        </div>

        <p className="form-helper-link">
          <Link className="text-link" to="/forgot-password">
            Forgot password?
          </Link>
        </p>

        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="form-footer">
          New to Gather?{' '}
          <Link className="text-link" to="/register">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);

    try {
      await forgotPassword(email.trim().toLowerCase());

      toast.success(
        'If that account can receive a reset code, it has been sent.'
      );

      navigate('/reset-password', {
        state: {
          email: email.trim().toLowerCase(),
        },
      });
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      pageLabel="A fresh start"
      title="Let’s get you"
      titleAccent="back in."
      description="We’ll send a short-lived code to the email address on your account."
    >
      <p className="card-kicker">Account recovery</p>
      <h2>Reset your password</h2>
      <p className="card-description">
        Enter the email address you used to register.
      </p>



      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="forgot-email">Email address</label>
          <input
            id="forgot-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Sending code…' : 'Send reset code'}
        </button>

        <p className="form-footer">
          <Link className="text-link" to="/login">
            Back to sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  const location = useLocation();

  const [email, setEmail] = useState(location.state?.email || '');
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();

    if (password !== confirmation) {
      toast.error('Passwords do not match.');
      return;
    }

    setBusy(true);

    try {
      await resetPassword({
        email: email.trim().toLowerCase(),
        otp,
        new_password: password,
        password_confirm: confirmation,
      });

      toast.success('Your password has been updated. You can sign in now.');
      setOtp('');
      setPassword('');
      setConfirmation('');
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      pageLabel="One last step"
      title="A new password,"
      titleAccent="then you’re in."
      description="Use the code we emailed you to choose a new password."
    >
      <p className="card-kicker">Account recovery</p>
      <h2>Choose a new password</h2>



      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="reset-email">Email address</label>
          <input
            id="reset-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="reset-otp">6-digit code</label>
          <input
            id="reset-otp"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={otp}
            onChange={(event) =>
              setOtp(
                event.target.value.replace(/\D/g, '').slice(0, 6)
              )
            }
            required
          />
        </div>

        <div className="field">
          <label htmlFor="new-password">New password</label>

          <div className="password-field">
            <input
              id="new-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
          </div>
        </div>

        <div className="field">
          <label htmlFor="confirm-password">Confirm new password</label>

          <div className="password-field">
            <input
              id="confirm-password"
              type={showConfirmation ? 'text' : 'password'}
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              required
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() =>
                setShowConfirmation((current) => !current)
              }
              aria-label={
                showConfirmation ? 'Hide password' : 'Show password'
              }
            >
              {showConfirmation ? '🙈' : '👁️'}
            </button>
          </div>
        </div>

        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Updating…' : 'Update password'}
        </button>

        <p className="form-footer">
          <Link className="text-link" to="/login">
            Back to sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

