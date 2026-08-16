const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  const token = localStorage.getItem("crm_token");

  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    // Response has no JSON body.
  }

  if (response.status === 401 && path !== "/api/auth/login") {
    localStorage.removeItem("crm_token");
    localStorage.removeItem("crm_user");
    window.location.reload();
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const message =
      data?.detail?.message ||
      data?.detail ||
      `Request failed (${response.status})`;

    throw new Error(
      typeof message === "string"
        ? message
        : JSON.stringify(message)
    );
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

  customers: async ({ search = "", status = "", page = 1, limit = 50, signal } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
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

  dashboardStats: () => request("/api/dashboard/stats"),

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

  deleteFollowup: (id) =>
    request(`/api/followups/${id}`, {
      method: "DELETE",
    }),

  importAnalyze: (file, sheet = "") =>
    uploadRequest("/api/import/analyze", file, sheet),

  importPreview: (file, sheet = "") =>
    uploadRequest("/api/import/preview", file, sheet),

  importFile: (file, sheet = "") =>
    uploadRequest("/api/import/import", file, sheet),
};
