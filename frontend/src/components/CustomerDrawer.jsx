import { Phone, Plus, CalendarClock, X, CheckCircle2 } from "lucide-react";
import { formatDate } from "../utils/formatters";

function Detail({ label, value, wide }) {
  return (
    <div className={wide ? "detail wide" : "detail"}>
      <span>{label}</span>
      <strong>{value || "—"}</strong>
    </div>
  );
}

export function CustomerDrawer({
  customer,
  calls,
  followups,
  onClose,
  onCall,
  onFollowup,
  onComplete,
}) {
  return (
    <div className="drawer-layer">
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="customer-drawer">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Customer details</p>
            <h2>{customer.name}</h2>
          </div>
          <button className="icon-button" onClick={onClose}>
            <X size={19} />
          </button>
        </div>

        <div className="drawer-actions">
          {customer.phone && (
            <a className="button primary" href={`tel:${customer.phone}`}>
              <Phone size={17} />
              Call {customer.phone}
            </a>
          )}
          <button className="button secondary" onClick={onCall}>
            <Plus size={17} /> Log call
          </button>
          <button className="button secondary" onClick={onFollowup}>
            <CalendarClock size={17} /> Follow-up
          </button>
        </div>

        <div className="detail-card">
          <div className="detail">
            <span>Phone</span>
            {customer.phone ? (
              <a href={`tel:${customer.phone}`} className="phone-detail">
                <Phone size={15} />
                {customer.phone}
              </a>
            ) : (
              <strong>—</strong>
            )}
          </div>
          <Detail label="Email" value={customer.email} />
          <Detail label="Consumer number" value={customer.consumer_number} />
          <Detail label="Service" value={customer.service} />
          <Detail label="Region" value={customer.region} />
          <Detail label="Zone" value={customer.zone} />
          <Detail label="Circle" value={customer.circle} />
          <Detail label="Division" value={customer.division} />
          <Detail label="Subdivision" value={customer.subdivision} />
          <Detail label="Business unit" value={customer.business_unit} />
          <Detail label="Address" value={customer.address} wide />
        </div>

        <section className="drawer-section">
          <div className="section-heading">
            <div>
              <h3>Follow-ups</h3>
              <span>Scheduled callbacks</span>
            </div>
          </div>
          {followups.length ? (
            followups.map((f) => (
              <div className="history-row" key={f.id}>
                <div>
                  <strong>
                    {formatDate(f.followup_date)} {f.followup_time || ""}
                  </strong>
                  <span>
                    {f.reason || "Follow-up"}
                    {f.notes ? ` · ${f.notes}` : ""}
                  </span>
                </div>
                {f.status === "pending" && (
                  <button
                    className="complete-button"
                    onClick={() => onComplete(f.id)}
                  >
                    <CheckCircle2 size={18} />
                  </button>
                )}
              </div>
            ))
          ) : (
            <span className="muted-text">No follow-ups yet.</span>
          )}
        </section>

        <section className="drawer-section">
          <div className="section-heading">
            <div>
              <h3>Call history</h3>
              <span>{calls.length} recorded call{calls.length === 1 ? "" : "s"}</span>
            </div>
          </div>
          {calls.length ? (
            calls.map((call) => (
              <div className="history-row" key={call.id}>
                <div>
                  <strong>{call.call_status.replaceAll("_", " ")}</strong>
                  <span>{new Date(call.called_at).toLocaleString("en-IN")}</span>
                  {call.notes && <small>{call.notes}</small>}
                </div>
              </div>
            ))
          ) : (
            <span className="muted-text">No calls recorded yet.</span>
          )}
        </section>
      </aside>
    </div>
  );
}
