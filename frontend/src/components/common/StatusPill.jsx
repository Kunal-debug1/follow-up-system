export function StatusPill({ status }) {
  const normalized = (status || "new").toLowerCase().replaceAll("_", "-");
  return (
    <span className={`status-pill status-${normalized}`}>
      {status || "New"}
    </span>
  );
}
