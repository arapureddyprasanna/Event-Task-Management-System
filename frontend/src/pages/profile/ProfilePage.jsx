import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePassword, updateProfile } from '../../api/auth';
import { getApiErrorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { PageHeader } from '../../components/common/States';
import toast from 'react-hot-toast';

function ProfilePage({ admin = false }) {
  const { user, refreshProfile, signOut } = useAuth();
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', password_confirm: '' });
  const [profileError, setProfileError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (user) setForm({ first_name: user.first_name || '', last_name: user.last_name || '', email: user.email || '' });
  }, [user]);

  const saveProfile = async (event) => {
    event.preventDefault(); setProfileError(''); setSavingProfile(true);
    const emailChanged = form.email.trim().toLowerCase() !== user.email.toLowerCase();
    try {
      await updateProfile({ first_name: form.first_name.trim(), last_name: form.last_name.trim(), ...(emailChanged ? { email: form.email.trim().toLowerCase() } : {}) });
      if (emailChanged) {
        const nextEmail = form.email.trim().toLowerCase();
        await signOut();
        navigate('/verify-email', { state: { email: nextEmail } });
      } else {
        await refreshProfile();
        toast.success('Your profile has been updated.');
      }
    } catch (requestError) { setProfileError(getApiErrorMessage(requestError)); }
    finally { setSavingProfile(false); }
  };

  const savePassword = async (event) => {
    event.preventDefault(); setPasswordError('');
    if (passwords.new_password !== passwords.password_confirm) { setPasswordError('Passwords do not match.'); return; }
    setSavingPassword(true);
    try {
      await changePassword(passwords);
      setPasswords({ current_password: '', new_password: '', password_confirm: '' });
      toast.success('Password changed successfully.');
      await signOut();
      navigate('/login', { replace: true, state: { notice: 'Password changed. Please sign in again.' } });
    } catch (requestError) { setPasswordError(getApiErrorMessage(requestError)); }
    finally { setSavingPassword(false); }
  };

  const logout = async () => {
    if (!window.confirm('Are you sure you want to log out?')) return;
    await signOut();
    toast.success('Logged out successfully.');
    navigate('/login', { replace: true });
  };

  return <><PageHeader eyebrow={admin ? 'Administrator profile' : 'Your account'} title="Your profile.">Manage the personal details and password connected to your Gather account.</PageHeader><div className="profile-layout"><section className="editor-card profile-card"><div className="profile-identity"><div className="avatar avatar-large">{(user?.first_name || user?.username || 'G').slice(0, 1).toUpperCase()}</div><div><p className="eyebrow">{admin ? 'STAFF ACCOUNT' : 'GATHER MEMBER'}</p><h2>{user?.first_name ? `${user.first_name} ${user.last_name || ''}` : user?.username}</h2><span>@{user?.username}</span></div></div><form onSubmit={saveProfile}><div className="form-grid"><label className="form-field"><span>First name</span><input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} maxLength={150} /></label><label className="form-field"><span>Last name</span><input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} maxLength={150} /></label><label className="form-field form-field-full"><span>Username</span><input value={user?.username || ''} disabled /><small>Usernames are managed by the account system.</small></label><label className="form-field form-field-full"><span>Email address</span><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /><small>Changing your email requires verification before you can use Gather again.</small></label></div>{profileError && <div className="inline-alert" role="alert">{profileError}</div>}<div className="form-actions"><button className="button button-dark" type="submit" disabled={savingProfile}>{savingProfile ? 'Saving…' : 'Save profile'}</button></div></form><div className="profile-meta"><span>Email status</span><strong>{user?.is_email_verified ? 'Verified' : 'Verification required'}</strong></div><div className="form-actions"><button className="button button-danger" type="button" onClick={logout}>Logout ↗</button></div></section><section className="editor-card password-card"><p className="eyebrow">Account security</p><h2>Change password</h2><p className="muted-copy">After changing your password, you’ll sign in again with the new one.</p><form onSubmit={savePassword}><label className="form-field"><span>Current password</span><input type="password" autoComplete="current-password" value={passwords.current_password} onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} required /></label><label className="form-field"><span>New password</span><input type="password" autoComplete="new-password" value={passwords.new_password} onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} required /></label><label className="form-field"><span>Confirm new password</span><input type="password" autoComplete="new-password" value={passwords.password_confirm} onChange={(e) => setPasswords({ ...passwords, password_confirm: e.target.value })} required /></label>{passwordError && <div className="inline-alert" role="alert">{passwordError}</div>}<button className="button button-dark" type="submit" disabled={savingPassword}>{savingPassword ? 'Updating…' : 'Update password'}</button></form></section></div></>;
}

export default ProfilePage;
