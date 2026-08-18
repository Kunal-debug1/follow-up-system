import { CalendarClock, ChevronRight, Users, Clock3, AlertCircle, CheckCircle2 } from "lucide-react";
import { EmptyState } from "./common/EmptyState";
import { formatDate } from "../utils/formatters";

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={19} /></div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function FollowupList({ items, onCustomer, onComplete }) {
  return (
    <div className="followup-list">
      {items.map((item) => (
        <div className="followup-row" key={item.id}>
          <div className="time-block">
            <strong>{item.followup_time || "—"}</strong>
            <span>{formatDate(item.followup_date)}</span>
          </div>
          <div className="followup-main">
            <button onClick={() => onCustomer({ id: item.customer_id })}>
              <strong>{item.customer_name || `Customer #${item.customer_id}`}</strong>
            </button>
            <span>
              {item.reason || "Follow-up"}
              {item.notes ? ` · ${item.notes}` : ""}
            </span>
          </div>
          {onComplete && (
            <button
              className="complete-button"
              onClick={() => onComplete(item)}
              title="Mark completed"
            >
              <CheckCircle2 size={18} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export function Dashboard({ loading, stats, today, upcoming, customers, onCustomer, onFollowups }) {
  return (
    <div className="page-content">
      <section className="welcome">
        <div>
          <p className="eyebrow">Overview</p>
          <h2>Keep every customer follow-up on track.</h2>
          <p>See today's callbacks, manage customers and keep your call history organized.</p>
        </div>
        <button className="button primary" onClick={onFollowups}>
          <CalendarClock size={17} /> View follow-ups
        </button>
      </section>

      <section className="stat-grid">
        <StatCard icon={Users} label="Total customers" value={loading ? "…" : stats.total_customers.toLocaleString()} />
        <StatCard icon={Clock3} label="Today's follow-ups" value={loading ? "…" : stats.today_followups} />
        <StatCard icon={AlertCircle} label="Overdue follow-ups" value={loading ? "…" : stats.overdue_followups} />
        <StatCard icon={CalendarClock} label="Next 7 days" value={loading ? "…" : stats.upcoming_followups} />
      </section>

      <section className="content-grid">
        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Today's follow-ups</h3>
              <span>Callbacks that need attention today</span>
            </div>
            <button className="text-button" onClick={onFollowups}>
              View all <ChevronRight size={16} />
            </button>
          </div>
          {today.length === 0 ? (
            <EmptyState icon={CalendarClock} title="No follow-ups today" text="Your callback list is clear." />
          ) : (
            <FollowupList items={today.slice(0, 6)} onCustomer={onCustomer} />
          )}
        </div>

        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Recent customers</h3>
              <span>Latest imported contacts</span>
            </div>
          </div>
          {customers.length === 0 ? (
            <EmptyState icon={Users} title="No customers found" text="Import your customer data to get started." />
          ) : (
            <div className="mini-list">
              {customers.slice(0, 6).map((customer) => (
                <button key={customer.id} className="mini-row" onClick={() => onCustomer(customer)}>
                  <div className="avatar soft">
                    {(customer.name || "?").charAt(0).toUpperCase()}
                  </div>
                  <div className="mini-info">
                    <strong>{customer.name}</strong>
                    <span>{customer.phone || customer.email || customer.consumer_number || "No contact detail"}</span>
                  </div>
                  <ChevronRight size={17} className="muted" />
                </button>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// Re-export FollowupList for use by other pages
export { FollowupList };
