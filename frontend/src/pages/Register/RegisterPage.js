import { useState } from 'react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

import AuthLayout from '../../components/AuthLayout';
import FormMessage from '../../components/FormMessage';

import { getApiErrorMessage } from '../../services/api';
import { register } from '../../services/authService';

const emptyForm = {
  username: '',
  email: '',
  password: '',
  password_confirm: '',
  first_name: '',
  last_name: '',
  role: 'user',
};

const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordChecks(password, confirmation) {
  return [
    {
      label: 'At least 8 characters',
      passed: password.length >= 8,
    },
    {
      label: 'At least one uppercase letter',
      passed: /[A-Z]/.test(password),
    },
    {
      label: 'At least one lowercase letter',
      passed: /[a-z]/.test(password),
    },
    {
      label: 'At least one number',
      passed: /\d/.test(password),
    },
    {
      label: 'At least one special character',
      passed: /[^A-Za-z0-9]/.test(password),
    },
    {
      label: 'Password and confirmation match',
      passed:
        Boolean(confirmation) &&
        password === confirmation,
    },
  ];
}

function RegisterPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] =
    useState(false);

  const checks = passwordChecks(
    form.password,
    form.password_confirm
  );

  const passwordRequirementsMet = checks
    .slice(0, 5)
    .every(({ passed }) => passed);

  const passwordMismatch =
    Boolean(form.password_confirm) &&
    form.password !== form.password_confirm;

  const updateField = (event) => {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));

    setFieldErrors((current) => ({
      ...current,
      [name]: '',
    }));

    setError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError('');

    const normalizedUsername = form.username.trim();
    const email = form.email.trim().toLowerCase();

    const localErrors = {};

    if (!normalizedUsername) {
      localErrors.username =
        'Please enter a username.';
    }

    if (!email) {
      localErrors.email =
        'Please enter your email address.';
    } else if (!validEmail.test(email)) {
      localErrors.email =
        'Please enter a valid email address.';
    }

    if (!form.password) {
      localErrors.password =
        'Please enter a password.';
    } else if (!passwordRequirementsMet) {
      localErrors.password =
        'Password does not meet all the listed requirements.';
    }

    if (!form.password_confirm) {
      localErrors.password_confirm =
        'Please confirm your password.';
    } else if (
      form.password !== form.password_confirm
    ) {
      localErrors.password_confirm =
        'Passwords do not match.';
    }

    setFieldErrors(localErrors);

    if (Object.keys(localErrors).length > 0) {
      return;
    }

    setIsSubmitting(true);

    try {
      const { data } = await register({
        username: normalizedUsername,
        email,
        password: form.password,
        password_confirm: form.password_confirm,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        role: form.role,
      });

      /*
       * Registration succeeded.
       *
       * The backend should:
       * - create the account
       * - mark email as unverified
       * - generate a verification code
       * - send the code to the user's email
       */

      setForm(emptyForm);
      setFieldErrors({});
      setError('');

      navigate('/verify-email', {
        replace: true,
        state: {
          email,
          notice:
            data?.detail ||
            'We sent a verification code to your email address.',
        },
      });
    } catch (requestError) {
      const data = requestError?.response?.data;

      if (data?.email) {
        toast.error(
          'This email is already registered. Please use a different email.'
        );

        setForm(emptyForm);
        setFieldErrors({});
        setError('');
      } else if (data?.username) {
        toast.error(
          'This username is already registered. Please choose a different username.'
        );

        setForm(emptyForm);
        setFieldErrors({});
        setError('');
      } else {
        setError(
          getApiErrorMessage(requestError)
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const fieldError = (name) =>
    fieldErrors[name] && (
      <span
        className="field-error"
        id={`${name}-error`}
        role="alert"
      >
        {fieldErrors[name]}
      </span>
    );

  return (
    <AuthLayout
      pageLabel="Make room for good plans"
      title="Bring your people"
      titleAccent="together."
      description="Create a space for the events you’re looking forward to and the little things that make them happen."
    >
      <p className="card-kicker">
        Your account
      </p>

      <h2>Create your account</h2>

      <p className="card-description">
        A few details and you’re on your way.
      </p>

      <FormMessage>{error}</FormMessage>

      <form
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="field-grid">

          {/* ACCOUNT TYPE */}

          <div className="field full-width">
            <span className="field-label">
              Account type
            </span>

            <div className="registration-role-options">

              <label htmlFor="role-user">
                <input
                  id="role-user"
                  name="role"
                  type="radio"
                  value="user"
                  checked={
                    form.role === 'user'
                  }
                  onChange={updateField}
                />

                <span>User</span>
              </label>

              <label htmlFor="role-admin">
                <input
                  id="role-admin"
                  name="role"
                  type="radio"
                  value="admin"
                  checked={
                    form.role === 'admin'
                  }
                  onChange={updateField}
                />

                <span>Admin</span>
              </label>

            </div>

            {form.role === 'admin' && (
              <span className="field-hint">
                Admin access requires email
                verification and superuser
                approval.
              </span>
            )}
          </div>

          {/* FIRST NAME */}

          <div className="field">
            <label htmlFor="first_name">
              First name{' '}
              <span className="optional">
                Optional
              </span>
            </label>

            <input
              id="first_name"
              name="first_name"
              autoComplete="given-name"
              value={form.first_name}
              onChange={updateField}
              placeholder="Sam"
            />
          </div>

          {/* LAST NAME */}

          <div className="field">
            <label htmlFor="last_name">
              Last name{' '}
              <span className="optional">
                Optional
              </span>
            </label>

            <input
              id="last_name"
              name="last_name"
              autoComplete="family-name"
              value={form.last_name}
              onChange={updateField}
              placeholder="Taylor"
            />
          </div>

          {/* USERNAME */}

          <div className="field full-width">
            <label htmlFor="username">
              Username
            </label>

            <input
              id="username"
              name="username"
              autoComplete="username"
              value={form.username}
              onChange={updateField}
              placeholder="Choose a username"
              required
              aria-invalid={
                Boolean(fieldErrors.username)
              }
              aria-describedby={
                fieldErrors.username
                  ? 'username-error'
                  : undefined
              }
            />

            {fieldError('username')}
          </div>

          {/* EMAIL */}

          <div className="field full-width">
            <label htmlFor="email">
              Email address
            </label>

            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              inputMode="email"
              value={form.email}
              onChange={updateField}
              placeholder="you@example.com"
              required
              aria-invalid={
                Boolean(fieldErrors.email)
              }
              aria-describedby={
                fieldErrors.email
                  ? 'email-error'
                  : undefined
              }
            />

            {fieldError('email')}
          </div>

          {/* PASSWORD */}

          <div className="field full-width">
            <label htmlFor="password">
              Password
            </label>

            <div className="password-field">

              <input
                id="password"
                name="password"
                type={
                  showPassword
                    ? 'text'
                    : 'password'
                }
                autoComplete="new-password"
                value={form.password}
                onChange={updateField}
                placeholder="Create a password"
                required
                aria-invalid={
                  Boolean(
                    fieldErrors.password
                  )
                }
                aria-describedby={
                  fieldErrors.password
                    ? 'password-error password-hint'
                    : 'password-hint'
                }
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowPassword(
                    (current) => !current
                  )
                }
                aria-label={
                  showPassword
                    ? 'Hide password'
                    : 'Show password'
                }
              >
                {showPassword
                  ? '🙈'
                  : '👁️'}
              </button>

            </div>

            {fieldError('password')}

            <ul
              className="password-checklist"
              id="password-hint"
              aria-label="Password requirements"
            >
              {checks.map(
                ({ label, passed }) => (
                  <li
                    className={`password-check${passed
                        ? ' passed'
                        : ''
                      }`}
                    key={label}
                  >
                    <span aria-hidden="true">
                      {passed
                        ? '✓'
                        : '○'}
                    </span>

                    <span>
                      {label}
                    </span>
                  </li>
                )
              )}
            </ul>

          </div>

          {/* CONFIRM PASSWORD */}

          <div className="field full-width">

            <label htmlFor="password_confirm">
              Confirm password
            </label>

            <div className="password-field">

              <input
                id="password_confirm"
                name="password_confirm"
                type={
                  showConfirmation
                    ? 'text'
                    : 'password'
                }
                autoComplete="new-password"
                value={
                  form.password_confirm
                }
                onChange={updateField}
                placeholder="Enter your password again"
                required
                aria-invalid={Boolean(
                  fieldErrors.password_confirm ||
                  passwordMismatch
                )}
                aria-describedby={
                  fieldErrors.password_confirm ||
                    passwordMismatch
                    ? 'password_confirm-error'
                    : undefined
                }
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowConfirmation(
                    (current) => !current
                  )
                }
                aria-label={
                  showConfirmation
                    ? 'Hide confirmation password'
                    : 'Show confirmation password'
                }
              >
                {showConfirmation
                  ? '🙈'
                  : '👁️'}
              </button>

            </div>

            {fieldError(
              'password_confirm'
            )}

            {!fieldErrors.password_confirm &&
              passwordMismatch && (
                <span
                  className="field-error"
                  id="password_confirm-error"
                  role="alert"
                >
                  Passwords do not match.
                </span>
              )}

          </div>

        </div>

        <button
          className="primary-button"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting
            ? 'Creating your account…'
            : 'Create account'}
        </button>

        <p className="form-footer">
          By continuing, you agree to use
          Gather thoughtfully with your team.
        </p>

      </form>
    </AuthLayout>
  );
}

export default RegisterPage;