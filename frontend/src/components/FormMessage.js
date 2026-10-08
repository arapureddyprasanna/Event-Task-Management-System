function FormMessage({ children, tone = 'error' }) {
  if (!children) return null;
  return (
    <div className={`form-alert${tone === 'success' ? ' form-success' : ''}`} role={tone === 'success' ? 'status' : 'alert'} aria-live={tone === 'success' ? 'polite' : 'assertive'}>
      {children}
    </div>
  );
}

export default FormMessage;
