import { useState } from "react";
import { api } from "../api";
import { Modal } from "./common/Modal";

export function CustomerFormModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    email: "",
    consumer_number: "",
    service: "",
    address: "",
    notes: "",
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
      newErrors.consumer_number = "Phone or Consumer Number is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    try {
      setSaving(true);
      setApiError("");
      await api.createCustomer(formData);
      onSuccess();
    } catch (err) {
      // Use HTTP status from the error if available, otherwise check message
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
    <Modal title="Add Customer" onClose={onClose}>
      {apiError && <div className="form-error">{apiError}</div>}

      <p className="form-intro">
        Add the customer details available in your source record. Only a name
        and one contact identifier are required.
      </p>

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
          {errors.phone && !errors.name && (
            <div className="form-error">{errors.phone}</div>
          )}
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
        <div className={errors.consumer_number ? "form-field-error" : ""}>
          <label>Consumer Number</label>
          <input
            name="consumer_number"
            value={formData.consumer_number}
            onChange={handleChange}
            placeholder="Account or consumer ID"
          />
          {errors.consumer_number && (
            <div className="form-error">{errors.consumer_number}</div>
          )}
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

      <div>
        <label>Notes</label>
        <textarea
          name="notes"
          value={formData.notes}
          onChange={handleChange}
          placeholder="Optional notes"
        />
      </div>

      <div className="modal-actions">
        <button className="button secondary" onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button className="button primary" onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving..." : "Add Customer"}
        </button>
      </div>
    </Modal>
  );
}
