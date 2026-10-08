import { useState } from 'react';
import { Link } from 'react-router-dom';
import { createAdmin } from '../../api/auth';
import { getApiErrorMessage, getApiFieldErrors } from '../../api/client';
import { PageHeader } from '../../components/common/States';

const initialForm = { username: '', email: '', first_name: '', last_name: '', password: '', password_confirm: '' };

export default function CreateAdminPage() {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError(''); setNotice(''); setFieldErrors({});
    if (form.password !== form.password_confirm) {
      setFieldErrors({ password_confirm: 'Passwords do not match.' });
      return;
    }
    if (!window.confirm('Create a privileged administrator account? The new admin must verify their email before signing in.')) return;
    setBusy(true);
    try {
      const { data } = await createAdmin({ ...form, username: form.username.trim(), email: form.email.trim().toLowerCase() });
      setForm(initialForm);
      setNotice(data.detail || 'Admin account created. The new admin must verify their email before signing in.');
    } catch (requestError) {
      const errors = getApiFieldErrors(requestError);
      setFieldErrors(errors);
      setError(Object.keys(errors).length ? '' : getApiErrorMessage(requestError));
    } finally { setBusy(false); }
  };

  return <>
    <PageHeader eyebrow="Superuser management" title="Add an admin.">Create an administrator account for your organization. Email verification is required before the account can sign in.</PageHeader>
    {notice && <div className="inline-success" role="status">{notice} <Link className="text-link" to="/admin/users">View admin list</Link></div>}
    {error && <div className="inline-alert" role="alert">{error}</div>}
    <section className="editor-card admin-create-card">
      <h2>Create Admin</h2>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label className="form-field"><span>Username</span><input name="username" autoComplete="username" value={form.username} onChange={update} required maxLength={150} />{fieldErrors.username && <small className="field-error">{fieldErrors.username}</small>}</label>
          <label className="form-field"><span>Email address</span><input name="email" type="email" autoComplete="email" value={form.email} onChange={update} required />{fieldErrors.email && <small className="field-error">{fieldErrors.email}</small>}</label>
          <label className="form-field"><span>First name</span><input name="first_name" autoComplete="given-name" value={form.first_name} onChange={update} maxLength={150} /></label>
          <label className="form-field"><span>Last name</span><input name="last_name" autoComplete="family-name" value={form.last_name} onChange={update} maxLength={150} /></label>
          <label className="form-field"><span>Password</span><input name="password" type="password" autoComplete="new-password" value={form.password} onChange={update} required />{fieldErrors.password && <small className="field-error">{fieldErrors.password}</small>}</label>
          <label className="form-field"><span>Confirm password</span><input name="password_confirm" type="password" autoComplete="new-password" value={form.password_confirm} onChange={update} required />{fieldErrors.password_confirm && <small className="field-error" role="alert">{fieldErrors.password_confirm}</small>}</label>
        </div>
        <p className="admin-create-note">This account receives administrator access after creation. It cannot sign in until its email is verified.</p>
        <div className="form-actions"><button className="button button-dark" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create Admin'}</button></div>
      </form>
    </section>
  </>;
}
