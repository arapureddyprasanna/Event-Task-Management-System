import { useCallback, useEffect, useState } from 'react';
import {
  approveAdminAccessRequest,
  listAdminAccessRequests,
  rejectAdminAccessRequest,
} from '../../api/adminAccessRequests';
import { getApiErrorMessage } from '../../api/client';
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Pagination,
} from '../../components/common/States';

function AdminAccessRequestsPage() {
  const [payload, setPayload] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback((nextPage = 1) => {
    setLoading(true);
    setError('');
    listAdminAccessRequests({ status: 'pending', page: nextPage, page_size: 10 })
      .then(({ data }) => {
        setPayload(data);
        setPage(nextPage);
      })
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(1); }, [load]);

  const decide = async (adminRequest, decision) => {
    if (decision === 'reject' && !window.confirm(`Reject the admin access request from ${adminRequest.requester.username}?`)) return;
    setBusyId(adminRequest.id);
    setError('');
    setNotice('');
    try {
      if (decision === 'approve') await approveAdminAccessRequest(adminRequest.id);
      else await rejectAdminAccessRequest(adminRequest.id);
      setNotice(decision === 'approve' ? 'Admin access approved.' : 'Admin access request rejected.');
      load(1);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Superuser review" title="Admin access requests.">
        Review requests before an applicant receives admin permissions.
      </PageHeader>
      {notice && <div className="inline-success" role="status">{notice}</div>}
      {error && <div className="inline-alert" role="alert">{error}</div>}
      {loading ? <LoadingState label="Loading admin access requests…" /> : error && !payload ? (
        <ErrorState message={error} onRetry={() => load(page)} />
      ) : payload?.results?.length ? (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Applicant</th><th>Email</th><th>Requested</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>{payload.results.map((item) => (
                <tr key={item.id}>
                  <td><strong>{[item.requester.first_name, item.requester.last_name].filter(Boolean).join(' ') || item.requester.username}</strong><small>@{item.requester.username}</small></td>
                  <td>{item.requester.email}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td><span className="status-pill pending">Pending</span></td>
                  <td className="admin-request-actions">
                    <button className="button button-dark button-small" type="button" disabled={busyId === item.id} onClick={() => decide(item, 'approve')}>{busyId === item.id ? 'Saving…' : 'Approve'}</button>
                    <button className="button button-quiet button-small" type="button" disabled={busyId === item.id} onClick={() => decide(item, 'reject')}>Reject</button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <Pagination page={page} pages={Math.ceil(payload.count / 10)} onChange={load} />
        </>
      ) : (
        <EmptyState title="No pending requests">New admin access requests will appear here for review.</EmptyState>
      )}
    </>
  );
}

export default AdminAccessRequestsPage;
