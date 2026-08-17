import { AlertTriangle, X } from "lucide-react";

/**
 * A reusable confirmation dialog.
 *
 * Props:
 *   title        — dialog title
 *   message      — main message text
 *   subMessage   — smaller secondary message (optional)
 *   confirmLabel — text for the confirm button (default: "Confirm")
 *   cancelLabel  — text for cancel button (default: "Cancel")
 *   danger       — if true, the confirm button is styled as destructive (red)
 *   onConfirm    — called when the user clicks confirm
 *   onCancel     — called when the user clicks cancel or backdrop
 *   loading      — if true, confirm button shows loading state
 */
export function ConfirmModal({
  title,
  message,
  subMessage,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
  loading = false,
}) {
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" onClick={onCancel} />
      <div className="modal confirm-modal">
        <div className="modal-header">
          <div className="confirm-modal-icon-wrap">
            <AlertTriangle size={20} className={danger ? "confirm-icon-danger" : "confirm-icon-warn"} />
          </div>
          <h3>{title}</h3>
          <button className="icon-button" onClick={onCancel}>
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">
          <p className="confirm-modal-message">{message}</p>
          {subMessage && (
            <p className="confirm-modal-sub">{subMessage}</p>
          )}
          <div className="modal-actions">
            <button
              className="button secondary"
              onClick={onCancel}
              disabled={loading}
            >
              {cancelLabel}
            </button>
            <button
              className={`button ${danger ? "btn-danger" : "primary"}`}
              onClick={onConfirm}
              disabled={loading}
            >
              {loading ? "Please wait…" : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
