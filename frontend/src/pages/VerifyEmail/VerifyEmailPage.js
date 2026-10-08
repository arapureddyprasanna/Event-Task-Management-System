import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import AuthLayout from '../../components/AuthLayout';
import FormMessage from '../../components/FormMessage';
import { getApiErrorMessage } from '../../services/api';
import { resendOtp, verifyEmail } from '../../services/authService';

function VerifyEmailPage() {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email || '');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(location.state?.email ? 'We sent a verification code to this address.' : '');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  const handleVerify = async (event) => {
    event.preventDefault();
    setIsVerifying(true);
    try {
      await verifyEmail({ email: email.trim().toLowerCase(), otp });
      toast.success('Your email is verified. Sign in to continue to Gather.');
      setOtp('');
      setIsVerified(true);
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError));
    } finally {
      setIsVerifying(false);
    }
  };

  const handleResend = async () => {
    setIsResending(true);
    try {
      await resendOtp({ email: email.trim().toLowerCase() });
      setOtp('');
      toast.success('A new verification code has been sent.');
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError));
    } finally {
      setIsResending(false);
    }
  };

  const updateEmail = (event) => {
    setEmail(event.target.value);
    setIsVerified(false);
  };

  const updateOtp = (event) => {
    setOtp(event.target.value.replace(/\D/g, '').slice(0, 6));

  };

  return (
    <AuthLayout
      pageLabel="One quick check"
      title="Check your"
      titleAccent="inbox."
      description="We’ll make sure we have the right email before you start planning with your people."
    >
      <p className="card-kicker">Email verification</p>
      <h2>Enter your code</h2>
      <p className="card-description">We sent a six-digit verification code to:</p>
      <form onSubmit={handleVerify} noValidate>
        <div className="field">
          <label htmlFor="verify-email">Email address</label>
          <input id="verify-email" name="email" type="email" autoComplete="email" inputMode="email" value={email} onChange={updateEmail} placeholder="you@example.com" required />
        </div>
        <div className="verification-email" aria-live="polite">{email || 'Enter the address you registered with'}</div>

        <div className="field">
          <label htmlFor="otp">6-digit code</label>
          <input
            id="otp"
            className="otp-input"
            name="otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            value={otp}
            onChange={updateOtp}
            placeholder="••••••"
            aria-describedby="otp-hint"
            required
          />
          <span className="field-hint" id="otp-hint">The code expires after 10 minutes.</span>
        </div>
        <div className="verify-actions">
          <button className="primary-button" type="submit" disabled={isVerified || isVerifying || isResending || !email || otp.length !== 6}>
            {isVerifying ? 'Checking code…' : 'Verify email'}
          </button>
          {!isVerified && (
            <div className="resend-row">
              <span>Didn’t receive a code?</span>
              <button className="subtle-action" type="button" onClick={handleResend} disabled={isResending || isVerifying || !email}>
                {isResending ? 'Sending…' : 'Resend code'}
              </button>
            </div>
          )}
        </div>
      </form>
      <p className="form-footer">{isVerified ? <Link className="text-link" to="/login">Continue to sign in</Link> : <Link className="text-link" to="/register">Back to registration</Link>}</p>
    </AuthLayout>
  );
}

export default VerifyEmailPage;
