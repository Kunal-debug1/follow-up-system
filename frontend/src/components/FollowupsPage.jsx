import { CalendarClock, CheckCircle2 } from "lucide-react";
import { EmptyState } from "./common/EmptyState";
import { FollowupList } from "./Dashboard";

export function FollowupsPage({ overdue, today, upcoming, onCustomer, onComplete }) {
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Callbacks</p>
          <h2>Follow-ups</h2>
          <p>Never lose a promised callback.</p>
        </div>
      </div>

      <div className="content-grid">
        {overdue.length > 0 && (
          <div className="card" style={{ gridColumn: "1 / -1", border: "1px solid #fecaca" }}>
            <div className="section-heading" style={{ background: "#fef2f2" }}>
              <div>
                <h3 style={{ color: "#b42318" }}>Overdue</h3>
                <span>{overdue.length} overdue callback{overdue.length === 1 ? "" : "s"}</span>
              </div>
            </div>
            <FollowupList items={overdue} onCustomer={onCustomer} onComplete={onComplete} />
          </div>
        )}

        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Today</h3>
              <span>{today.length} pending callback{today.length === 1 ? "" : "s"}</span>
            </div>
          </div>
          {today.length ? (
            <FollowupList items={today} onCustomer={onCustomer} onComplete={onComplete} />
          ) : (
            <EmptyState icon={CheckCircle2} title="You're all caught up" text="No pending callbacks today." />
          )}
        </div>

        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Next 7 days</h3>
              <span>{upcoming.length} scheduled callback{upcoming.length === 1 ? "" : "s"}</span>
            </div>
          </div>
          {upcoming.length ? (
            <FollowupList items={upcoming} onCustomer={onCustomer} onComplete={onComplete} />
          ) : (
            <EmptyState icon={CalendarClock} title="No upcoming follow-ups" text="Schedule one from a customer profile." />
          )}
        </div>
      </div>
    </div>
  );
}
