import { memo } from "react";
import { CalendarClock, CheckCircle2 } from "lucide-react";
import { EmptyState } from "./common/EmptyState";
import { formatDate } from "../utils/formatters";

const OUTCOME_LABELS = {
  interested: "Interested",
  not_interested: "Not Interested",
  call_back: "Call Back",
  no_answer: "No Answer",
  busy: "Busy",
  converted: "Converted",
};

const PRIORITY_CLASS = {
  high: "priority-high",
  medium: "priority-medium",
  low: "priority-low",
};

const FollowupRow = memo(function FollowupRow({ item, onCustomer, onComplete }) {
  return (
    <div className="followup-row">
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
          {item.outcome && (
            <> · <span className={`outcome-pill outcome-${item.outcome}`}>
              {OUTCOME_LABELS[item.outcome] || item.outcome}
            </span></>
          )}
        </span>
        {item.notes && <small className="followup-notes-preview">{item.notes}</small>}
      </div>
      <div className="followup-meta">
        {item.priority && item.priority !== "medium" && (
          <span className={`priority-badge ${PRIORITY_CLASS[item.priority]}`}>
            {item.priority}
          </span>
        )}
        {onComplete && item.status === "pending" && (
          <button
            className="complete-button"
            onClick={() => onComplete(item)}
            title="Mark completed"
          >
            <CheckCircle2 size={18} />
          </button>
        )}
      </div>
    </div>
  );
});

const FollowupSection = memo(function FollowupSection({ title, subtitle, items, onCustomer, onComplete, accentClass }) {
  return (
    <div className={`card followup-section-card ${accentClass || ""}`}>
      <div className="section-heading">
        <div>
          <h3>{title}</h3>
          <span>{subtitle}</span>
        </div>
      </div>
      <div className="followup-list">
        {items.map((item) => (
          <FollowupRow
            key={item.id}
            item={item}
            onCustomer={onCustomer}
            onComplete={onComplete}
          />
        ))}
      </div>
    </div>
  );
});

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

      <div className="content-grid followups-grid">
        {overdue.length > 0 && (
          <FollowupSection
            title="Overdue"
            subtitle={`${overdue.length} overdue callback${overdue.length === 1 ? "" : "s"}`}
            items={overdue}
            onCustomer={onCustomer}
            onComplete={onComplete}
            accentClass="card-overdue"
          />
        )}

        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Today</h3>
              <span>{today.length} pending callback{today.length === 1 ? "" : "s"}</span>
            </div>
          </div>
          {today.length ? (
            <div className="followup-list">
              {today.map((item) => (
                <FollowupRow
                  key={item.id}
                  item={item}
                  onCustomer={onCustomer}
                  onComplete={onComplete}
                />
              ))}
            </div>
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
            <div className="followup-list">
              {upcoming.map((item) => (
                <FollowupRow
                  key={item.id}
                  item={item}
                  onCustomer={onCustomer}
                  onComplete={onComplete}
                />
              ))}
            </div>
          ) : (
            <EmptyState icon={CalendarClock} title="No upcoming follow-ups" text="Schedule one from a customer profile." />
          )}
        </div>
      </div>
    </div>
  );
}
