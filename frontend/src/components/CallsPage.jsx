import { Phone, ChevronRight } from "lucide-react";

export function CallsPage({ calls, onCustomer }) {
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Activity</p>
          <h2>Call history</h2>
          <p>Recent calls logged across all customers.</p>
        </div>
      </div>
      <div className="card">
        <div className="section-heading">
          <div>
            <h3>Recent calls</h3>
            <span>Select a customer to see their full profile and notes.</span>
          </div>
        </div>
        <div className="mini-list">
          {calls.length === 0 ? (
            <div className="empty-state">
              <Phone size={32} className="muted" />
              <h4>No recent calls</h4>
              <p>Log a call from a customer's profile to see it here.</p>
            </div>
          ) : (
            calls.map((call) => (
              <button
                className="mini-row"
                key={call.id}
                onClick={() => onCustomer({ id: call.customer_id })}
              >
                <div className="avatar soft"><Phone size={17} /></div>
                <div className="mini-info">
                  <strong>{call.customer_name}</strong>
                  <span>
                    {call.call_status.replaceAll("_", " ")}
                    {call.notes ? ` · ${call.notes}` : ""}
                  </span>
                  <small>
                    {new Date(call.called_at).toLocaleString("en-IN", {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </small>
                </div>
                <ChevronRight size={17} className="muted" />
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
