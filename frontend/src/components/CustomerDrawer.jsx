import { useState, useRef } from "react";
import {
  Phone,
  Plus,
  CalendarClock,
  X,
  CheckCircle2,
  Edit2,
  Archive,
  RotateCcw,
  Trash2,
  MessageCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { formatDate } from "../utils/formatters";
import { api, whatsappUrl } from "../api";
import { CustomerTimeline } from "./CustomerTimeline";

// Priority badge colors
const PRIORITY_CLASS = {
  high: "priority-high",
  medium: "priority-medium",
  low: "priority-low",
};

const PRIORITY_LABELS = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const OUTCOME_LABELS = {
  interested: "Interested",
  not_interested: "Not Interested",
  call_back: "Call Back",
  no_answer: "No Answer",
  busy: "Busy",
  converted: "Converted",
};

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
  onEdit,
  onArchive,
  onRestore,
  onPermanentDelete,
  timelineRefreshKey,
  onWhatsAppLogged,
}) {
  const [showTimeline, setShowTimeline] = useState(false);
  // Prevent duplicate WhatsApp activity records on double-click
  const whatsappLoggingRef = useRef(false);

  const waUrl = whatsappUrl(customer.phone);

  /**
   * Record a WhatsApp activity when the user intentionally clicks the button.
   * We fire-and-forget the API call — the WhatsApp link still opens regardless.
   * A ref guard ensures only one record is created even on rapid double-clicks.
   */
  const handleWhatsAppClick = async () => {
    if (!customer.id || whatsappLoggingRef.current) return;
    whatsappLoggingRef.current = true;
    try {
      await api.createCall(customer.id, {
        call_status: "whatsapp",
        notes: null,
      });
      // Notify parent so it can refresh call history and timeline
      if (onWhatsAppLogged) onWhatsAppLogged();
    } catch {
      // Non-critical — WhatsApp still opens; log silently
      console.warn("WhatsApp activity could not be recorded.");
    } finally {
      // Allow re-recording after a short cooldown (e.g. if they reopen)
      setTimeout(() => { whatsappLoggingRef.current = false; }, 5000);
    }
  };

  return (
    <div className="drawer-layer">
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="customer-drawer">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">
              {customer.is_archived ? (
                <span className="archived-badge">Archived</span>
              ) : (
                "Customer details"
              )}
            </p>
            <h2>{customer.name}</h2>
          </div>
          <button className="icon-button" onClick={onClose}>
            <X size={19} />
          </button>
        </div>

        {/* Primary actions */}
        <div className="drawer-actions">
          {customer.phone && (
            <a className="button primary" href={`tel:${customer.phone}`}>
              <Phone size={17} />
              Call {customer.phone}
            </a>
          )}
          {waUrl && (
            <a
              className="button whatsapp-btn"
              href={waUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Open WhatsApp"
              onClick={handleWhatsAppClick}
            >
              <MessageCircle size={17} />
              WhatsApp
            </a>
          )}
          {!customer.is_archived && (
            <>
              <button className="button secondary" onClick={onCall}>
                <Plus size={17} /> Log call
              </button>
              <button className="button secondary" onClick={onFollowup}>
                <CalendarClock size={17} /> Follow-up
              </button>
            </>
          )}
        </div>

        {/* Management actions */}
        <div className="drawer-mgmt-actions">
          <button className="mgmt-btn" onClick={onEdit} title="Edit customer">
            <Edit2 size={15} /> Edit
          </button>
          {customer.is_archived ? (
            <button
              className="mgmt-btn restore"
              onClick={onRestore}
              title="Restore customer"
            >
              <RotateCcw size={15} /> Restore
            </button>
          ) : (
            <button
              className="mgmt-btn archive"
              onClick={onArchive}
              title="Archive customer"
            >
              <Archive size={15} /> Archive
            </button>
          )}
          <button
            className="mgmt-btn delete"
            onClick={onPermanentDelete}
            title="Permanently delete customer (admin only)"
          >
            <Trash2 size={15} /> Delete
          </button>
        </div>

        {/* Customer info card */}
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
          <div className="detail">
            <span>Status</span>
            <strong className={`status-pill status-${(customer.status || "new").replace("_", "-")}`}>
              {customer.status || "new"}
            </strong>
          </div>
          <div className="detail">
            <span>Priority</span>
            <strong className={`priority-badge ${PRIORITY_CLASS[customer.priority] || "priority-medium"}`}>
              {PRIORITY_LABELS[customer.priority] || "Medium"}
            </strong>
          </div>
          <Detail label="Region" value={customer.region} />
          <Detail label="Zone" value={customer.zone} />
          <Detail label="Circle" value={customer.circle} />
          <Detail label="Division" value={customer.division} />
          <Detail label="Subdivision" value={customer.subdivision} />
          <Detail label="Business unit" value={customer.business_unit} />
          <Detail label="Address" value={customer.address} wide />
          {customer.notes && (
            <Detail label="Notes" value={customer.notes} wide />
          )}
          {customer.is_archived && customer.archived_at && (
            <div className="detail wide archived-info">
              <span>Archived</span>
              <strong>
                {new Date(customer.archived_at).toLocaleDateString("en-IN", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                })}
                {customer.archived_by ? ` by ${customer.archived_by}` : ""}
              </strong>
            </div>
          )}
        </div>

        {/* Follow-ups section */}
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
                  <div className="followup-row-header">
                    <strong>
                      {formatDate(f.followup_date)} {f.followup_time || ""}
                    </strong>
                    <span className={`status-pill status-${f.status}`}>
                      {f.status}
                    </span>
                    {f.priority && f.priority !== "medium" && (
                      <span className={`priority-badge ${PRIORITY_CLASS[f.priority]}`}>
                        {PRIORITY_LABELS[f.priority]}
                      </span>
                    )}
                  </div>
                  <span>
                    {f.reason || "Follow-up"}
                    {f.outcome && (
                      <> · <span className={`outcome-pill outcome-${f.outcome}`}>
                        {OUTCOME_LABELS[f.outcome] || f.outcome}
                      </span></>
                    )}
                  </span>
                  {f.notes && <small>{f.notes}</small>}
                </div>
                {f.status === "pending" && (
                  <button
                    className="complete-button"
                    onClick={() => onComplete(f)}
                    title="Mark as completed"
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

        {/* Call history section */}
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

        {/* Timeline section */}
        <section className="drawer-section">
          <div className="section-heading">
            <div>
              <h3>Timeline</h3>
              <span>Full customer history</span>
            </div>
            <button
              className="text-button"
              onClick={() => setShowTimeline((v) => !v)}
            >
              {showTimeline ? (
                <><ChevronUp size={15} /> Hide</>
              ) : (
                <><ChevronDown size={15} /> Show</>
              )}
            </button>
          </div>
          {showTimeline && (
            <div className="timeline-wrap">
              <CustomerTimeline
                customerId={customer.id}
                refreshKey={timelineRefreshKey}
              />
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}
