export function Field({ label, children, full = false }) {
  return <label className={`form-field${full ? ' form-field-full' : ''}`}><span>{label}</span>{children}</label>;
}
