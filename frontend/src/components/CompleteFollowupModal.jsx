import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api } from "../api";
import { Modal } from "./common/Modal";

const OUTCOMES = [
  ["interested", "Interested"],
  ["not_interested", "Not Interested"],
  ["call_back", "Call Back"],
  ["no_answer", "No Answer"],
  ["busy", "Busy"],
  ["converted", "Converted"],
];

// Outcomes that typically warrant scheduling a next follow-up
const NEXT_FOLLOWUP_SUGGESTED = new Set(["interested", "call_back", "busy", "no_answer"]);

/**
 * Complete Follow-up Modal
 *
 * Provides a guided workflow for completing a follow-up:
 *  1. Select outcome
 *  2. Add notes
 *  3. Optionally schedule next follow-up
 *
 * Props:
 *   followup  — the follow-up object to complete
 *   onClose   — called to dismiss the modal
 *   onSuccess — called with { completed, next_followup } after successful completion
 */
export function CompleteFollowupModal({ followup, onClose, onSuccess }) {
  const [outcome, setOutcome] = useState("interested");
  const [notes, setNotes] = useState(followup.notes || "");
  const [createNext, setCreateNext] = useState(
    NEXT_FOLLOWUP_SUGGESTED.has("interested")
  );
  const [nextDate, setNextDate] = useState("");
  const [nextTime, setNextTime] = useState("");
  const [nextReason, setNextReason] = useState(followup.reason || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Update createNext suggestion when outcome changes
  const handleOutcomeChange = (e) => {
    const val = e.target.value;
    setOutcome(val);
    setCreateNext(NEXT_FOLLOWUP_SUGGESTED.has(val));
  };

  // Compute tomorrow as default minimum for next follow-up date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = tomorrow.toISOString().split("T")[0];

  const handleSubmit = async () => {
    if (createNext && !nextDate) {
      setError("Please select a date for the next follow-up.");
      return;
    }
    if (createNext && nextDate < new Date().toISOString().split("T")[0]) {
      setError("Next follow-up date cannot be in the past.");
      return;
    }

    try {
      setSaving(true);
      setError("");
      const result = await api.completeFollowup(followup.id, {
        outcome,
        notes: notes || null,
        create_next: createNext,
        next_date: createNext ? nextDate : null,
        next_time: createNext && nextTime ? nextTime : null,
        next_reason: createNext && nextReason ? nextReason : null,
      });
      onSuccess(result);
    } catch (err) {
      setError(err.message || "Failed to complete follow-up.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Complete Follow-up" onClose={onClose}>
      {error && <div className="form-error api-error">{error}</div>}

      <p className="form-intro">
        Record the outcome of this follow-up.
        {followup.followup_date && (
          <> Scheduled for <strong>{followup.followup_date}</strong>{followup.followup_time ? ` at ${followup.followup_time}` : ""}.</>
        )}
      </p>

      <label>Outcome *</label>
      <select value={outcome} onChange={handleOutcomeChange}>
        {OUTCOMES.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>

      <label>Notes</label>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="What happened? Any important details…"
        rows={3}
      />

      <div className="next-followup-toggle">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={createNext}
            onChange={(e) => setCreateNext(e.target.checked)}
          />
          <span>Schedule next follow-up</span>
        </label>
      </div>

      {createNext && (
        <div className="next-followup-fields">
          <div className="form-grid">
            <div>
              <label>Next Date *</label>
              <input
                type="date"
                value={nextDate}
                min={tomorrowStr}
                onChange={(e) => setNextDate(e.target.value)}
              />
            </div>
            <div>
              <label>Time (optional)</label>
              <input
                type="time"
                value={nextTime}
                onChange={(e) => setNextTime(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label>Reason (optional)</label>
            <input
              value={nextReason}
              onChange={(e) => setNextReason(e.target.value)}
              placeholder="e.g. Customer requested callback"
            />
          </div>
        </div>
      )}

      <div className="modal-actions">
        <button className="button secondary" onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button
          className="button primary"
          onClick={handleSubmit}
          disabled={saving}
        >
          <CheckCircle2 size={16} />
          {saving ? "Saving…" : "Complete Follow-up"}
        </button>
      </div>
    </Modal>
  );
}
