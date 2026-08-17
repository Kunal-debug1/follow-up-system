import { useEffect, useState } from "react";
import {
  UserPlus,
  Phone,
  CalendarClock,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
} from "lucide-react";
import { api } from "../api";

const EVENT_ICONS = {
  created: UserPlus,
  call: Phone,
  followup: CalendarClock,
};

const FOLLOWUP_STATUS_ICONS = {
  completed: CheckCircle2,
  pending: Clock,
  missed: AlertCircle,
  cancelled: XCircle,
};

const OUTCOME_LABELS = {
  interested: "Interested",
  not_interested: "Not Interested",
  call_back: "Call Back",
  no_answer: "No Answer",
  busy: "Busy",
  converted: "Converted",
};

function TimelineIcon({ eventType, status }) {
  let Icon = EVENT_ICONS[eventType] || CalendarClock;
  if (eventType === "followup" && status) {
    Icon = FOLLOWUP_STATUS_ICONS[status] || CalendarClock;
  }
  return (
    <div className={`timeline-icon timeline-icon-${eventType} timeline-icon-status-${status || ""}`}>
      <Icon size={14} />
    </div>
  );
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Customer Timeline
 *
 * Fetches and renders a chronological list of events for a customer.
 * Events include: customer creation, call logs, and follow-ups.
 *
 * Props:
 *   customerId — the customer's ID
 *   refreshKey — increment to force a reload (e.g., after adding a call/followup)
 */
export function CustomerTimeline({ customerId, refreshKey }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    api.customerTimeline(customerId)
      .then((data) => {
        if (!cancelled) setEvents(data || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load timeline");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [customerId, refreshKey]);

  if (loading) {
    return <div className="timeline-loading">Loading timeline…</div>;
  }

  if (error) {
    return <div className="timeline-error">{error}</div>;
  }

  if (events.length === 0) {
    return <div className="timeline-empty">No events yet.</div>;
  }

  return (
    <div className="timeline">
      {events.map((event, idx) => (
        <div key={`${event.event_type}-${event.event_id}-${idx}`} className="timeline-item">
          <div className="timeline-connector">
            <TimelineIcon eventType={event.event_type} status={event.status} />
            {idx < events.length - 1 && <div className="timeline-line" />}
          </div>
          <div className="timeline-content">
            <div className="timeline-title">{event.title}</div>
            {event.outcome && (
              <span className={`outcome-pill outcome-${event.outcome}`}>
                {OUTCOME_LABELS[event.outcome] || event.outcome}
              </span>
            )}
            {event.subtitle && (
              <div className="timeline-subtitle">{event.subtitle}</div>
            )}
            {event.notes && (
              <div className="timeline-notes">"{event.notes}"</div>
            )}
            <div className="timeline-time">{formatTimestamp(event.timestamp)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
