import { useState } from "react";
import { api } from "../api";
import { Modal } from "./common/Modal";

const STATUSES = [
  ["new", "New"],
  ["contacted", "Contacted"],
  ["interested", "Interested"],
  ["not_interested", "Not Interested"],
  ["converted", "Converted"],
];

const PRIORITIES = [
  ["low", "Low"],
  ["medium", "Medium"],
  ["high", "High"],
];

/**
 * Edit Customer Modal
 *
 * Allows editing all customer fields including name, phone, email,
 * and consumer_number (with server-side duplicate detection).
 *
 * Props:
 *   customer  — the existing customer object
 *   onClose   — called to dismiss the modal
 *   onSuccess — called with the updated customer after a successful save
 */
export function EditCustomerModal({ customer, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: customer.name || "",
    phone: customer.phone || "",
    email: customer.email || "",
    consumer_number: customer.consumer_number || "",
    service: customer.service || "",
    address: customer.address || "",
    region: customer.region || "",
    zone: customer.zone || "",
    circle: customer.circle || "",
    division: customer.division || "",
    subdivision: customer.subdivision || "",
    business_unit: customer.business_unit || "",
    status: customer.status || "new",
    priority: customer.priority || "medium",
    notes: customer.notes || "",
  });

  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (errors[e.target.name]) {
      setErrors({ ...errors, [e.target.name]: "" });
    }
    if (apiError) setApiError("");
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.name.trim()) newErrors.name = "Name is required";
    if (!formData.phone.trim() && !formData.consumer_number.trim()) {
      newErrors.phone = "Phone or Consumer Number is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    try {
      setSaving(true);
      setApiError("");

      // Build patch payload — only send fields that actually changed
      const patch = {};
      const fields = [
        "name", "phone", "email", "consumer_number", "service", "address",
        "region", "zone", "circle", "division", "subdivision", "business_unit",
        "status", "priority", "notes",
      ];
      for (const key of fields) {
        const original = String(customer[key] ?? "");
        const current = formData[key] ?? "";
        if (current !== original) {
          patch[key] = current || null;
        }
      }

      if (Object.keys(patch).length === 0) {
        onClose();
        return;
      }

      const updated = await api.updateCustomer(customer.id, patch);
      onSuccess(updated);
    } catch (err) {
      if (err.status === 409 || err.message?.toLowerCase().includes("already exists")) {
        setApiError("A customer with this phone or consumer number already exists.");
      } else {
        setApiError(err.message || "An unexpected error occurred.");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Edit Customer" onClose={onClose}>
      {apiError && <div className="form-error api-error">{apiError}</div>}

      <div className="form-grid">
        <div className={errors.name ? "form-field-error" : ""}>
          <label>Customer Name *</label>
          <input
            name="name"
            value={formData.name}
            onChange={handleChange}
            placeholder="John Doe"
          />
          {errors.name && <div className="form-error">{errors.name}</div>}
        </div>
        <div className={errors.phone ? "form-field-error" : ""}>
          <label>Mobile Number</label>
          <input
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="9876543210"
          />
          {errors.phone && <div className="form-error">{errors.phone}</div>}
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Email</label>
          <input
            name="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="john@example.com"
          />
        </div>
        <div>
          <label>Consumer Number</label>
          <input
            name="consumer_number"
            value={formData.consumer_number}
            onChange={handleChange}
            placeholder="Account or consumer ID"
          />
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Service</label>
          <input
            name="service"
            value={formData.service}
            onChange={handleChange}
            placeholder="Service or product"
          />
        </div>
        <div>
          <label>Address</label>
          <input
            name="address"
            value={formData.address}
            onChange={handleChange}
            placeholder="Full address"
          />
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Region</label>
          <input name="region" value={formData.region} onChange={handleChange} placeholder="Region" />
        </div>
        <div>
          <label>Zone</label>
          <input name="zone" value={formData.zone} onChange={handleChange} placeholder="Zone" />
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Circle</label>
          <input name="circle" value={formData.circle} onChange={handleChange} placeholder="Circle" />
        </div>
        <div>
          <label>Division</label>
          <input name="division" value={formData.division} onChange={handleChange} placeholder="Division" />
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Subdivision</label>
          <input name="subdivision" value={formData.subdivision} onChange={handleChange} placeholder="Subdivision" />
        </div>
        <div>
          <label>Business Unit</label>
          <input name="business_unit" value={formData.business_unit} onChange={handleChange} placeholder="Business unit" />
        </div>
      </div>

      <div className="form-grid">
        <div>
          <label>Status</label>
          <select name="status" value={formData.status} onChange={handleChange}>
            {STATUSES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Priority</label>
          <select name="priority" value={formData.priority} onChange={handleChange}>
            {PRIORITIES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label>Notes</label>
        <textarea
          name="notes"
          value={formData.notes}
          onChange={handleChange}
          placeholder="Optional notes"
          rows={3}
        />
      </div>

      <div className="modal-actions">
        <button className="button secondary" onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button className="button primary" onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </Modal>
  );
}
