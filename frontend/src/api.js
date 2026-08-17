const API_BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const token = localStorage.getItem('crm_token');
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (response.status === 401 && path !== '/api/auth/login') {
    localStorage.removeItem('crm_token');
    localStorage.removeItem('crm_user');
    window.location.reload();
    throw new Error('Session expired');
  }

  if (!response.ok) {
    const message =
      data?.detail?.message ||
      data?.detail ||
      `Request failed (${response.status})`;

    const error = new Error(
      typeof message === "string" ? message : JSON.stringify(message)
    );
    // Attach the HTTP status code to the error so callers can branch on it
    // without string-matching the error message.
    error.status = response.status;
    throw error;
  }

  return data;
}

function normalizePhone(value) {
  if (value === null || value === undefined) {
    return null;
  }

  const phone = String(value)
    .trim()
    .replace(/\.0$/, "");

  return phone || null;
}

function normalizeCustomer(customer) {
  if (!customer || typeof customer !== "object") {
    return customer;
  }

  return {
    ...customer,

    id: customer.id,

    name:
      customer.name ??
      customer.customer_name ??
      customer.consumer_name ??
      "",

    phone: normalizePhone(
      customer.phone ??
      customer.mobile ??
      customer.mobile_number ??
      customer.phone_number ??
      customer.contact_number
    ),

    email:
      customer.email ??
      customer.email_address ??
      null,

    consumer_number:
      customer.consumer_number ??
      customer.consumer_no ??
      customer.consumerNumber ??
      null,

    address: customer.address ?? null,
    region: customer.region ?? null,
    zone: customer.zone ?? null,
    circle: customer.circle ?? null,
    division: customer.division ?? null,
    subdivision: customer.subdivision ?? null,
    business_unit:
      customer.business_unit ??
      customer.businessUnit ??
      null,

    status: customer.status ?? "new",
    priority: customer.priority ?? "medium",
    is_archived: customer.is_archived ?? false,
    archived_at: customer.archived_at ?? null,
    archived_by: customer.archived_by ?? null,
  };
}

function normalizeCustomers(data) {
  if (Array.isArray(data)) {
    return data.map(normalizeCustomer);
  }

  if (Array.isArray(data?.items)) {
    return data.items.map(normalizeCustomer);
  }

  if (Array.isArray(data?.customers)) {
    return data.customers.map(normalizeCustomer);
  }

  return [];
}

/**
 * Generate a WhatsApp URL for a phone number.
 * Assumes Indian numbers (10-digit → prepend 91).
 * Returns null if no valid phone is available.
 */
export function whatsappUrl(phone) {
  if (!phone) return null;
  const digits = String(phone).replace(/\D/g, "");
  if (!digits) return null;
  // Prepend India country code if it's a 10-digit number
  const normalized = digits.length === 10 ? `91${digits}` : digits;
  return `https://wa.me/${normalized}`;
}

async function uploadRequest(path, file, sheet = "") {
  const form = new FormData();
  form.append("file", file);

  const query = sheet ? `?sheet=${encodeURIComponent(sheet)}` : "";

  return request(`${path}${query}`, {
    method: "POST",
    body: form,
  });
}

export const api = {
  login: (username, password) => request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  }),

  logout: () => {
    localStorage.removeItem('crm_token');
    localStorage.removeItem('crm_user');
    window.location.reload();
  },

  health: () => request("/api/health"),

  // ---------------------------------------------------------------------------
  // Customers
  // ---------------------------------------------------------------------------

  customers: async ({ search = "", status = "", page = 1, limit = 50, signal, archived = false } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (archived) params.set("archived", "true");
    params.set("page", String(page));
    params.set("limit", String(limit));
    const query = params.toString();
    const data = await request(`/api/customers${query ? `?${query}` : ""}`, { signal });
    // Normalize items within paginated response
    return {
      ...data,
      items: (data.items || []).map(normalizeCustomer),
    };
  },

  customer: async (id) => {
    const data = await request(`/api/customers/${id}`);
    return normalizeCustomer(data);
  },

  createCustomer: (body) =>
    request("/api/customers", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),

  updateCustomer: (id, body) =>
    request(`/api/customers/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  archiveCustomer: (id) =>
    request(`/api/customers/${id}/archive`, {
      method: "POST",
    }),

  restoreCustomer: (id) =>
    request(`/api/customers/${id}/restore`, {
      method: "POST",
    }),

  deleteCustomerPermanently: (id) =>
    request(`/api/customers/${id}`, {
      method: "DELETE",
    }),

  customerTimeline: (id) =>
    request(`/api/customers/${id}/timeline`),

  // ---------------------------------------------------------------------------
  // Dashboard
  // ---------------------------------------------------------------------------

  dashboardStats: () => request("/api/dashboard/stats"),

  // ---------------------------------------------------------------------------
  // Calls
  // ---------------------------------------------------------------------------

  calls: (id, limit = 50) =>
    request(`/api/customers/${id}/calls?limit=${limit}`),

  createCall: (id, body) =>
    request(`/api/customers/${id}/calls`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),

  // ---------------------------------------------------------------------------
  // Follow-ups
  // ---------------------------------------------------------------------------

  followups: (id, status = "") => {
    const params = new URLSearchParams();

    if (status) {
      params.set("status", status);
    }

    const query = params.toString();

    return request(
      `/api/customers/${id}/followups${query ? `?${query}` : ""}`
    );
  },

  createFollowup: (id, body) =>
    request(`/api/customers/${id}/followups`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),

  todayFollowups: () => request("/api/followups/today"),

  upcomingFollowups: (days = 7) =>
    request(`/api/followups/upcoming?days=${days}`),
    
  overdueFollowups: () => request("/api/followups/overdue"),

  updateFollowup: (id, body) =>
    request(`/api/followups/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),

  completeFollowup: (id, body) =>
    request(`/api/followups/${id}/complete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),

  deleteFollowup: (id) =>
    request(`/api/followups/${id}`, {
      method: "DELETE",
    }),

  // ---------------------------------------------------------------------------
  // Import
  // ---------------------------------------------------------------------------

  importAnalyze: (file, sheet = "") =>
    uploadRequest("/api/import/analyze", file, sheet),

  importPreview: (file, sheet = "") =>
    uploadRequest("/api/import/preview", file, sheet),

  importFile: (file, sheet = "") =>
    uploadRequest("/api/import/import", file, sheet),
};
