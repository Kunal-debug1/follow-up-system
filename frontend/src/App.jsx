import { useEffect, useRef, useState } from "react";
import {
  Bell,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  Clock3,
  Eye,
  FileSpreadsheet,
  LayoutDashboard,
  LogOut,
  Menu,
  Phone,
  Plus,
  Search,
  Users,
  X,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { api } from "./api";

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "customers", label: "Customers", icon: Users },
  { id: "followups", label: "Follow-ups", icon: CalendarClock },
  { id: "calls", label: "Call History", icon: Phone },
  { id: "import", label: "Import Data", icon: FileSpreadsheet },
];

const CALL_STATUSES = [
  ["interested", "Interested"],
  ["busy", "Busy"],
  ["no_answer", "No Answer"],
  ["call_later", "Call Later"],
  ["not_interested", "Not Interested"],
  ["converted", "Converted"],
];

function formatDate(value) {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
function displayPhone(phone) {
  if (phone === null || phone === undefined) {
    return "—";
  }

  const value = String(phone).trim();

  return value || "—";
}

function StatusPill({ status }) {
  const normalized = (status || "new").toLowerCase().replaceAll("_", "-");
  return <span className={`status-pill status-${normalized}`}>{status || "New"}</span>;
}

function EmptyState({ icon: Icon = ClipboardList, title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={22} /></div>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function LoginPage({ onLogin, error, loading }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(username, password);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="brand-mark">C</div>
          <h1>CRM Follow-Up</h1>
          <p>Sign in to access your workspace</p>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="login-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
          <div className="login-field">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              autoFocus
              required
            />
          </div>
          <div className="login-field">
            <label htmlFor="login-password">Password</label>
            <div className="password-input-wrap">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <X size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <button type="submit" className="button primary login-button" disabled={loading || !username || !password}>
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="login-footer">Admin access only</p>
      </div>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!localStorage.getItem('crm_token'));
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const handleLogin = async (username, password) => {
    try {
      setLoginLoading(true);
      setLoginError('');
      const data = await api.login(username, password);
      localStorage.setItem('crm_token', data.token);
      localStorage.setItem('crm_user', data.username);
      setIsAuthenticated(true);
    } catch (err) {
      setLoginError(err.message || 'Invalid credentials');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    api.logout();
  };

  const [activePage, setActivePage] = useState("dashboard");
  const [customers, setCustomers] = useState([]);
  
  // Pagination State
  const [page, setPage] = useState(1);
  const [totalCustomers, setTotalCustomers] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [pageLimit, setPageLimit] = useState(50);
  
  const [today, setToday] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [overdue, setOverdue] = useState([]);
  const [stats, setStats] = useState({
    total_customers: 0,
    today_followups: 0,
    overdue_followups: 0,
    upcoming_followups: 0,
    calls_today: 0
  });

  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerCalls, setCustomerCalls] = useState([]);
  const [customerFollowups, setCustomerFollowups] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  
  const [callModal, setCallModal] = useState(false);
  const [followupModal, setFollowupModal] = useState(false);
  const [customerModal, setCustomerModal] = useState(false);
  
  const [callStatus, setCallStatus] = useState("busy");
  const [callNotes, setCallNotes] = useState("");
  const [followupDate, setFollowupDate] = useState("");
  const [followupTime, setFollowupTime] = useState("");
  const [followupReason, setFollowupReason] = useState("Customer busy");
  const [followupNotes, setFollowupNotes] = useState("");
  const [saving, setSaving] = useState(false);
  
  const [toast, setToast] = useState(null);
  const customerRequestRef = useRef(null);
  const toastTimeoutRef = useRef(null);

  const showToast = (message, type = "success") => {
    clearTimeout(toastTimeoutRef.current);
    setToast({ message, type });
    toastTimeoutRef.current = setTimeout(() => setToast(null), 3000);
  };

  const loadOverview = async () => {
    try {
      setError("");
      const [todayData, upcomingData, overdueData, statsData] = await Promise.all([
        api.todayFollowups(),
        api.upcomingFollowups(7),
        api.overdueFollowups(),
        api.dashboardStats()
      ]);
      setToday(todayData);
      setUpcoming(upcomingData);
      setOverdue(overdueData);
      setStats(statsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadCustomers = async (searchTerm = '', p = 1, limit = pageLimit) => {
    customerRequestRef.current?.abort();
    const controller = new AbortController();
    customerRequestRef.current = controller;

    try {
      setLoading(true);
      const data = await api.customers({
        search: searchTerm,
        page: p,
        limit,
        signal: controller.signal,
      });
      if (customerRequestRef.current !== controller) return;
      setCustomers(data.items);
      setTotalCustomers(data.total);
      setTotalPages(data.pages);
      setPage(data.page);
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message);
    } finally {
      if (customerRequestRef.current === controller) {
        setLoading(false);
        customerRequestRef.current = null;
      }
    }
  };

  useEffect(() => () => {
    customerRequestRef.current?.abort();
    clearTimeout(toastTimeoutRef.current);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (activePage === "dashboard" || activePage === "followups") {
      loadOverview();
    }
  }, [activePage, isAuthenticated]);

  // Debounced Search
  useEffect(() => {
    if (!isAuthenticated) return;
    const timer = setTimeout(() => {
      loadCustomers(search, 1, pageLimit);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, pageLimit, isAuthenticated]);

  const openCustomer = async (customer) => {
    try {
      const [fullCustomer, calls, followups] = await Promise.all([
        api.customer(customer.id),
        api.calls(customer.id),
        api.followups(customer.id),
      ]);

      setSelectedCustomer(fullCustomer);
      setCustomerCalls(calls);
      setCustomerFollowups(followups);
    } catch (err) {
      setError(err.message);
    }
  };

  const closeCustomer = () => {
    setSelectedCustomer(null);
    setCallModal(false);
    setFollowupModal(false);
  };

  const saveCall = async () => {
    if (!selectedCustomer) return;
    try {
      setSaving(true);
      await api.createCall(selectedCustomer.id, {
        call_status: callStatus,
        notes: callNotes || null,
      });
      const calls = await api.calls(selectedCustomer.id);
      setCustomerCalls(calls);
      setCallModal(false);
      setCallNotes("");
      await loadOverview();
      showToast("Call logged successfully");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const saveFollowup = async () => {
    if (!selectedCustomer || !followupDate) return;
    try {
      setSaving(true);
      await api.createFollowup(selectedCustomer.id, {
        followup_date: followupDate,
        followup_time: followupTime || null,
        reason: followupReason || null,
        notes: followupNotes || null,
      });
      const followups = await api.followups(selectedCustomer.id);
      setCustomerFollowups(followups);
      setFollowupModal(false);
      setFollowupDate("");
      setFollowupTime("");
      setFollowupNotes("");
      await loadOverview();
      showToast("Follow-up scheduled successfully");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const completeFollowup = async (id) => {
    try {
      await api.updateFollowup(id, { status: "completed" });
      await loadOverview();
      if (selectedCustomer) {
        setCustomerFollowups(await api.followups(selectedCustomer.id));
      }
      showToast("Follow-up marked as completed");
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCustomerCreated = async () => {
    setCustomerModal(false);
    showToast("Customer created successfully");
    await loadCustomers(search, 1, pageLimit);
    await loadOverview();
  };

  const navigate = (id) => {
    setActivePage(id);
    setMobileNav(false);
    setSelectedCustomer(null);
  };

  const pageTitle = NAV.find((item) => item.id === activePage)?.label || "Dashboard";

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} error={loginError} loading={loginLoading} />;
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>CRM Follow-Up</strong>
            <span>Admin workspace</span>
          </div>
          <button className="mobile-close" onClick={() => setMobileNav(false)}><X size={19} /></button>
        </div>

        <nav className="nav-list">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${activePage === id ? "active" : ""}`}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="admin-card">
            <div className="avatar">A</div>
            <div>
              <strong>Administrator</strong>
              <span>Full access</span>
            </div>
            <button className="icon-button" onClick={handleLogout} title="Logout">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>

      {mobileNav && <div className="mobile-overlay" onClick={() => setMobileNav(false)} />}

      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={21} /></button>
          <div className="topbar-title">
            <span>Workspace</span>
            <h1>{pageTitle}</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" title="Notifications"><Bell size={19} /></button>
            <div className="top-avatar">A</div>
            <button className="icon-button" onClick={handleLogout} title="Logout"><LogOut size={18} /></button>
          </div>
        </header>

        {error && (
          <div className="alert error">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}><X size={17} /></button>
          </div>
        )}

        {activePage === "dashboard" && (
          <Dashboard
            loading={loading}
            stats={stats}
            today={today}
            upcoming={upcoming}
            customers={customers}
            onCustomer={openCustomer}
            onFollowups={() => navigate("followups")}
          />
        )}

        {activePage === "customers" && (
          <CustomersPage
            customers={customers}
            search={search}
            setSearch={setSearch}
            loading={loading}
            onCustomer={openCustomer}
            onCreateCustomer={() => setCustomerModal(true)}
            page={page}
            totalPages={totalPages}
            totalCustomers={totalCustomers}
            pageLimit={pageLimit}
            setPageLimit={setPageLimit}
            onPageChange={(p) => loadCustomers(search, p, pageLimit)}
          />
        )}

        {activePage === "followups" && (
          <FollowupsPage
            overdue={overdue}
            today={today}
            upcoming={upcoming}
            onCustomer={openCustomer}
            onComplete={completeFollowup}
          />
        )}

        {activePage === "calls" && (
          <CallsPage customers={customers} onCustomer={openCustomer} />
        )}

        {activePage === "import" && <ImportPage />}

        {selectedCustomer && (
          <CustomerDrawer
            customer={selectedCustomer}
            calls={customerCalls}
            followups={customerFollowups}
            onClose={closeCustomer}
            onCall={() => setCallModal(true)}
            onFollowup={() => setFollowupModal(true)}
            onComplete={completeFollowup}
          />
        )}

        {callModal && (
          <Modal title="Log a call" onClose={() => setCallModal(false)}>
            <label>Call result</label>
            <select value={callStatus} onChange={(e) => setCallStatus(e.target.value)}>
              {CALL_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <label>Notes</label>
            <textarea value={callNotes} onChange={(e) => setCallNotes(e.target.value)} placeholder="What happened on the call?" />
            <div className="modal-actions">
              <button className="button secondary" onClick={() => setCallModal(false)}>Cancel</button>
              <button className="button primary" onClick={saveCall} disabled={saving}>
                {saving ? "Saving..." : "Save call"}
              </button>
            </div>
          </Modal>
        )}

        {followupModal && (
          <Modal title="Schedule follow-up" onClose={() => setFollowupModal(false)}>
            <div className="form-grid">
              <div>
                <label>Date</label>
                <input type="date" value={followupDate} onChange={(e) => setFollowupDate(e.target.value)} />
              </div>
              <div>
                <label>Time</label>
                <input type="time" value={followupTime} onChange={(e) => setFollowupTime(e.target.value)} />
              </div>
            </div>
            <label>Reason</label>
            <input value={followupReason} onChange={(e) => setFollowupReason(e.target.value)} placeholder="Customer busy" />
            <label>Notes</label>
            <textarea value={followupNotes} onChange={(e) => setFollowupNotes(e.target.value)} placeholder="Add a short note..." />
            <div className="modal-actions">
              <button className="button secondary" onClick={() => setFollowupModal(false)}>Cancel</button>
              <button className="button primary" onClick={saveFollowup} disabled={saving || !followupDate}>
                {saving ? "Saving..." : "Schedule follow-up"}
              </button>
            </div>
          </Modal>
        )}

        {customerModal && (
          <CustomerFormModal
            onClose={() => setCustomerModal(false)}
            onSuccess={handleCustomerCreated}
          />
        )}

      </main>
      
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>
            {toast.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Dashboard({ loading, stats, today, upcoming, customers, onCustomer, onFollowups }) {
  return (
    <div className="page-content">
      <section className="welcome">
        <div>
          <p className="eyebrow">Overview</p>
          <h2>Keep every customer follow-up on track.</h2>
          <p>See today's callbacks, manage customers and keep your call history organized.</p>
        </div>
        <button className="button primary" onClick={onFollowups}><CalendarClock size={17} /> View follow-ups</button>
      </section>

      <section className="stat-grid">
        <StatCard icon={Users} label="Total customers" value={loading ? "…" : stats.total_customers.toLocaleString()} />
        <StatCard icon={Clock3} label="Today's follow-ups" value={loading ? "…" : stats.today_followups} />
        <StatCard icon={AlertCircle} label="Overdue follow-ups" value={loading ? "…" : stats.overdue_followups} />
        <StatCard icon={CalendarClock} label="Next 7 days" value={loading ? "…" : stats.upcoming_followups} />
      </section>

      <section className="content-grid">
        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Today's follow-ups</h3>
              <span>Callbacks that need attention today</span>
            </div>
            <button className="text-button" onClick={onFollowups}>View all <ChevronRight size={16} /></button>
          </div>
          {today.length === 0 ? (
            <EmptyState icon={CalendarClock} title="No follow-ups today" text="Your callback list is clear." />
          ) : (
            <FollowupList items={today.slice(0, 6)} onCustomer={onCustomer} />
          )}
        </div>

        <div className="card">
          <div className="section-heading">
            <div>
              <h3>Recent customers</h3>
              <span>Latest imported contacts</span>
            </div>
          </div>
          {customers.length === 0 ? (
            <EmptyState icon={Users} title="No customers found" text="Import your customer data to get started." />
          ) : (
            <div className="mini-list">
              {customers.slice(0, 6).map((customer) => (
                <button key={customer.id} className="mini-row" onClick={() => onCustomer(customer)}>
                  <div className="avatar soft">{(customer.name || "?").charAt(0).toUpperCase()}</div>
                  <div className="mini-info">
                    <strong>{customer.name}</strong>
                    <span>{customer.phone || customer.email || customer.consumer_number || "No contact detail"}</span>
                  </div>
                  <ChevronRight size={17} className="muted" />
                </button>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={19} /></div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function CustomersPage({ 
  customers, search, setSearch, loading, onCustomer, onCreateCustomer,
  page, totalPages, totalCustomers, pageLimit, setPageLimit, onPageChange
}) {
  return (
    <div className="page-content">
      <div className="page-heading">
        <div><p className="eyebrow">Customer database</p><h2>Customers</h2><p>Search and open a customer to manage calls and follow-ups.</p></div>
      </div>
      <div className="card">
        <div className="toolbar">
          <div className="search-box wide"><Search size={18} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, phone, consumer number, email..." /></div>
          <button className="button primary" onClick={onCreateCustomer}><Plus size={16} /> Add Customer</button>
        </div>
        {loading && customers.length === 0 ? <div className="loading">Loading customers…</div> : customers.length === 0 ? (
          <EmptyState icon={Users} title="No customers found" text="Try a different search." />
        ) : (
          <>
            <CustomerTable customers={customers} onCustomer={onCustomer} />
            <Pagination 
              page={page} 
              totalPages={totalPages} 
              totalItems={totalCustomers}
              limit={pageLimit}
              setLimit={setPageLimit}
              onPageChange={onPageChange}
              itemsLength={customers.length}
            />
          </>
        )}
      </div>
    </div>
  );
}

function CustomerTable({ customers, onCustomer }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Customer</th><th>Phone</th><th>Consumer no.</th><th>Location</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {customers.map((c) => (
            <tr key={c.id}>
              <td><button className="customer-link" onClick={() => onCustomer(c)}><span className="avatar soft small">{(c.name || "?").charAt(0).toUpperCase()}</span><span><strong>{c.name}</strong><small>{c.email || "No email"}</small></span></button></td>
              <td>
                {c.phone ? (
                  <a
                    href={`tel:${c.phone}`}
                    className="phone-link"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Phone size={14} />
                    {displayPhone(c.phone)}
                  </a>
                ) : (
                  <span className="muted-text">—</span>
                )}
              </td>
              <td>{c.consumer_number || "—"}</td>
              <td>{c.region || c.zone || "—"}</td>
              <td><StatusPill status={c.status} /></td>
              <td><button className="row-action" onClick={() => onCustomer(c)}><ChevronRight size={17} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({ page, totalPages, totalItems, limit, setLimit, onPageChange, itemsLength }) {
  const start = (page - 1) * limit + 1;
  const end = start + itemsLength - 1;

  return (
    <div className="pagination">
      <span>Showing {totalItems > 0 ? start : 0}-{end} of {totalItems} customers</span>
      <div className="pagination-controls">
        <select className="page-size-select" value={limit} onChange={e => setLimit(Number(e.target.value))}>
          <option value={25}>25 per page</option>
          <option value={50}>50 per page</option>
          <option value={100}>100 per page</option>
        </select>
        <button className="page-btn" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>{"<"}</button>
        <span style={{ padding: "0 8px" }}>Page {page} of {totalPages || 1}</span>
        <button className="page-btn" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>{">"}</button>
      </div>
    </div>
  );
}

function FollowupsPage({ overdue, today, upcoming, onCustomer, onComplete }) {
  return (
    <div className="page-content">
      <div className="page-heading"><div><p className="eyebrow">Callbacks</p><h2>Follow-ups</h2><p>Never lose a promised callback.</p></div></div>
      <div className="content-grid">
        
        {overdue.length > 0 && (
          <div className="card" style={{ gridColumn: "1 / -1", border: "1px solid #fecaca" }}>
            <div className="section-heading" style={{ background: "#fef2f2" }}><div><h3 style={{color: "#b42318"}}>Overdue</h3><span>{overdue.length} overdue callback{overdue.length === 1 ? "" : "s"}</span></div></div>
            <FollowupList items={overdue} onCustomer={onCustomer} onComplete={onComplete} />
          </div>
        )}

        <div className="card">
          <div className="section-heading"><div><h3>Today</h3><span>{today.length} pending callback{today.length === 1 ? "" : "s"}</span></div></div>
          {today.length ? <FollowupList items={today} onCustomer={onCustomer} onComplete={onComplete} /> : <EmptyState icon={CheckCircle2} title="You're all caught up" text="No pending callbacks today." />}
        </div>
        <div className="card">
          <div className="section-heading"><div><h3>Next 7 days</h3><span>{upcoming.length} scheduled callback{upcoming.length === 1 ? "" : "s"}</span></div></div>
          {upcoming.length ? <FollowupList items={upcoming} onCustomer={onCustomer} onComplete={onComplete} /> : <EmptyState icon={CalendarClock} title="No upcoming follow-ups" text="Schedule one from a customer profile." />}
        </div>
      </div>
    </div>
  );
}

function FollowupList({ items, onCustomer, onComplete }) {
  return (
    <div className="followup-list">
      {items.map((item) => {
        return (
          <div className="followup-row" key={item.id}>
            <div className="time-block"><strong>{item.followup_time || "—"}</strong><span>{formatDate(item.followup_date)}</span></div>
            <div className="followup-main">
              <button onClick={() => onCustomer({ id: item.customer_id })}><strong>{item.customer_name || `Customer #${item.customer_id}`}</strong></button>
              <span>{item.reason || "Follow-up"}{item.notes ? ` · ${item.notes}` : ""}</span>
            </div>
            {onComplete && <button className="complete-button" onClick={() => onComplete(item.id)} title="Mark completed"><CheckCircle2 size={18} /></button>}
          </div>
        );
      })}
    </div>
  );
}

function CallsPage({ customers, onCustomer }) {
  return (
    <div className="page-content">
      <div className="page-heading"><div><p className="eyebrow">Activity</p><h2>Call history</h2><p>Open a customer to view their complete call history.</p></div></div>
      <div className="card">
        <div className="section-heading"><div><h3>Customers with call activity</h3><span>Select a customer to see calls and notes.</span></div></div>
        <div className="mini-list">
          {customers.slice(0, 50).map((customer) => (
            <button className="mini-row" key={customer.id} onClick={() => onCustomer(customer)}>
              <div className="avatar soft"><Phone size={17} /></div>
              <div className="mini-info"><strong>{customer.name}</strong><span>{customer.phone || customer.consumer_number || "No contact detail"}</span></div>
              <ChevronRight size={17} className="muted" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ImportPage() {
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [preview, setPreview] = useState(null);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("upload");
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);
  const previewSummary = preview?.summary ?? {};

  const chooseFile = (nextFile) => {
    if (!nextFile) return;
    const valid = /\.(csv|xlsx|xls)$/i.test(nextFile.name);
    if (!valid) {
      setMessage("Please select a CSV, XLSX, or XLS file.");
      return;
    }
    setFile(nextFile);
    setAnalysis(null);
    setPreview(null);
    setSelectedSheet("");
    setMessage("");
    setStep("upload");
  };

  const analyze = async () => {
    if (!file) return;
    try {
      setBusy(true);
      setMessage("");
      const data = await api.importAnalyze(file, selectedSheet);
      setAnalysis(data);
      if (!selectedSheet && data.selected_sheet) setSelectedSheet(data.selected_sheet);
      setStep("analyzed");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  const previewData = async () => {
    if (!file) return;
    try {
      setBusy(true);
      setMessage("");
      const data = await api.importPreview(file, selectedSheet);
      setPreview(data);
      setStep("preview");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  const confirmImport = async () => {
    if (!file) return;
    const ok = window.confirm(
      `Import "${file.name}" into the CRM? This will add the records returned by the backend.`
    );
    if (!ok) return;

    try {
      setBusy(true);
      setMessage("");
      const data = await api.importFile(file, selectedSheet);
      setStep("complete");
      setMessage(
        `Import completed: ${data.imported_rows ?? 0} imported, ${data.duplicate_rows ?? 0} duplicates, ${data.skipped_rows ?? 0} skipped.`
      );
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setFile(null);
    setAnalysis(null);
    setPreview(null);
    setSelectedSheet("");
    setStep("upload");
    setMessage("");
  };

  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Data management</p>
          <h2>Import data</h2>
          <p>Upload customer data, analyze it, preview the records, then confirm the import.</p>
        </div>
      </div>

      <div className="import-wizard">
        <div className="import-progress">
          <ImportStep number="1" label="Upload" active={step === "upload"} done={!!analysis} />
          <ImportStep number="2" label="Analyze" active={step === "analyzed"} done={!!preview} />
          <ImportStep number="3" label="Preview" active={step === "preview"} done={step === "complete"} />
          <ImportStep number="4" label="Import" active={step === "complete"} done={false} />
        </div>

        <div className="card import-main">
          {!file && (
            <label
              className={`dropzone ${dragging ? "dragging" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                chooseFile(e.dataTransfer.files?.[0]);
              }}
            >
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => chooseFile(e.target.files?.[0])}
              />
              <div className="import-icon"><FileSpreadsheet size={30} /></div>
              <strong>Drop your customer file here</strong>
              <span>or click to browse</span>
              <small>CSV, XLSX or XLS</small>
            </label>
          )}

          {file && (
            <div className="selected-file">
              <div className="file-symbol"><FileSpreadsheet size={22} /></div>
              <div className="file-meta">
                <strong>{file.name}</strong>
                <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <button className="icon-button" onClick={reset} title="Remove file"><X size={17} /></button>
            </div>
          )}

          {analysis && analysis.sheets?.length > 0 && (
            <div className="sheet-select">
              <label>Sheet</label>
              <select
                value={selectedSheet || analysis.selected_sheet || ""}
                onChange={(e) => {
                  setSelectedSheet(e.target.value);
                  setAnalysis(null);
                  setPreview(null);
                  setStep("upload");
                }}
              >
                {analysis.sheets.map((sheet) => <option key={sheet} value={sheet}>{sheet}</option>)}
              </select>
              <span>Select the sheet containing customer records.</span>
            </div>
          )}

          {!analysis && file && (
            <div className="import-action-row">
              <div>
                <strong>Ready to analyze</strong>
                <span>We'll detect the header row and map contact fields.</span>
              </div>
              <button className="button primary" onClick={analyze} disabled={busy}>
                {busy ? "Analyzing..." : "Analyze file"}
              </button>
            </div>
          )}

          {analysis && (
            <div className="analysis-panel">
              <div className="analysis-header">
                <div>
                  <h3>Analysis complete</h3>
                  <span>Detected structure and contact fields</span>
                </div>
                <StatusPill status="Ready" />
              </div>

              <div className="analysis-stats">
                <AnalysisStat label="Rows" value={analysis.total_rows ?? 0} />
                <AnalysisStat label="Header row" value={analysis.header_row ?? "—"} />
                <AnalysisStat label="Sheet" value={analysis.selected_sheet || selectedSheet || "—"} />
                <AnalysisStat label="Required missing" value={analysis.missing_required?.length ?? 0} />
              </div>

              <div className="mapping-grid">
                {Object.entries(analysis.detected_mapping || {}).map(([key, value]) => (
                  <div className="mapping-item" key={key}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>{Array.isArray(value) ? value.join(", ") : value || "—"}</strong>
                  </div>
                ))}
              </div>

              {analysis.missing_required?.length > 0 && (
                <div className="import-warning">
                  <AlertCircle size={17} />
                  <span>Missing required fields: {analysis.missing_required.join(", ")}</span>
                </div>
              )}

              <div className="import-action-row">
                <div>
                  <strong>Next: preview the records</strong>
                  <span>Review what will be imported before changing the database.</span>
                </div>
                <button
                  className="button primary"
                  onClick={previewData}
                  disabled={busy || analysis.missing_required?.length > 0}
                >
                  {busy ? "Loading preview..." : "Preview records"}
                </button>
              </div>
            </div>
          )}

          {preview && (
            <div className="preview-panel">
              <div className="analysis-header">
                <div>
                  <h3>Import preview</h3>
                  <span>Review the records and duplicate summary before importing.</span>
                </div>
                <StatusPill status="Preview" />
              </div>

              <div className="preview-summary">
                <AnalysisStat label="Total rows" value={previewSummary.valid_records ?? preview.total_rows ?? preview.total ?? "—"} />
                <AnalysisStat label="New records" value={previewSummary.new_records ?? preview.new_count ?? "—"} />
                <AnalysisStat label="Already in DB" value={previewSummary.already_in_database ?? preview.duplicates ?? "—"} />
                <AnalysisStat label="Shown" value={(preview.rows || preview.preview || []).length} />
              </div>

              <PreviewTable data={preview.rows || preview.preview || preview.records || []} />

              <div className="import-action-row confirm-row">
                <div>
                  <strong>Everything look good?</strong>
                  <span>Confirm to save the imported records to the database.</span>
                </div>
                <button className="button primary" onClick={confirmImport} disabled={busy}>
                  {busy ? "Importing..." : "Confirm & import"}
                </button>
              </div>
            </div>
          )}

          {step === "complete" && (
            <div className="import-complete">
              <div className="complete-icon"><CheckCircle2 size={28} /></div>
              <h3>Import completed</h3>
              <p>{message || "Your customer data was imported successfully."}</p>
              <button className="button secondary" onClick={reset}>Import another file</button>
            </div>
          )}

          {message && step !== "complete" && (
            <div className="import-message">
              <AlertCircle size={17} />
              <span>{message}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ImportStep({ number, label, active, done }) {
  return (
    <div className={`import-step ${active ? "active" : ""} ${done ? "done" : ""}`}>
      <span>{done ? "✓" : number}</span>
      <strong>{label}</strong>
    </div>
  );
}

function AnalysisStat({ label, value }) {
  return (
    <div className="analysis-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PreviewTable({ data }) {
  if (!Array.isArray(data) || data.length === 0) {
    return <EmptyState icon={FileSpreadsheet} title="No preview rows returned" text="The backend did not return preview records." />;
  }

  const rows = data.slice(0, 100);
  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row || {})))
  ).slice(0, 10);

  return (
    <div className="preview-table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
               <tr key={index}>
              {columns.map((column) => (
                <td key={column} title={String(row?.[column] ?? "")}>
                  {String(row?.[column] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CustomerDrawer({ customer, calls, followups, onClose, onCall, onFollowup, onComplete }) {
  return (
    <div className="drawer-layer">
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="customer-drawer">
        <div className="drawer-header">
          <div><p className="eyebrow">Customer details</p><h2>{customer.name}</h2></div>
          <button className="icon-button" onClick={onClose}><X size={19} /></button>
        </div>
        <div className="drawer-actions">
         {customer.phone && (
          <a
            className="button primary"
            href={`tel:${customer.phone}`}
          >
            <Phone size={17} />
            Call {customer.phone}
          </a>
        )}
          <button className="button secondary" onClick={onCall}><Plus size={17} /> Log call</button>
          <button className="button secondary" onClick={onFollowup}><CalendarClock size={17} /> Follow-up</button>
        </div>

        <div className="detail-card">
          <div className="detail">
            <span>Phone</span>

            {customer.phone ? (
              <a
                href={`tel:${customer.phone}`}
                className="phone-detail"
              >
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
          <Detail label="Region" value={customer.region} />
          <Detail label="Zone" value={customer.zone} />
          <Detail label="Circle" value={customer.circle} />
          <Detail label="Division" value={customer.division} />
          <Detail label="Subdivision" value={customer.subdivision} />
          <Detail label="Business unit" value={customer.business_unit} />
          <Detail label="Address" value={customer.address} wide />
        </div>

        <section className="drawer-section">
          <div className="section-heading"><div><h3>Follow-ups</h3><span>Scheduled callbacks</span></div></div>
          {followups.length ? followups.map((f) => (
            <div className="history-row" key={f.id}>
              <div><strong>{formatDate(f.followup_date)} {f.followup_time || ""}</strong><span>{f.reason || "Follow-up"}{f.notes ? ` · ${f.notes}` : ""}</span></div>
              {f.status === "pending" && <button className="complete-button" onClick={() => onComplete(f.id)}><CheckCircle2 size={18} /></button>}
            </div>
          )) : <span className="muted-text">No follow-ups yet.</span>}
        </section>

        <section className="drawer-section">
          <div className="section-heading"><div><h3>Call history</h3><span>{calls.length} recorded call{calls.length === 1 ? "" : "s"}</span></div></div>
          {calls.length ? calls.map((call) => (
            <div className="history-row" key={call.id}>
              <div><strong>{call.call_status.replaceAll("_", " ")}</strong><span>{new Date(call.called_at).toLocaleString("en-IN")}</span>{call.notes && <small>{call.notes}</small>}</div>
            </div>
          )) : <span className="muted-text">No calls recorded yet.</span>}
        </section>
      </aside>
    </div>
  );
}

function Detail({ label, value, wide }) {
  return <div className={wide ? "detail wide" : "detail"}><span>{label}</span><strong>{value || "—"}</strong></div>;
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal">
        <div className="modal-header"><h3>{title}</h3><button className="icon-button" onClick={onClose}><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function CustomerFormModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    email: "",
    consumer_number: "",
    service: "",
    address: "",
    notes: ""
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    // clear related error
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
      if (err.message.includes("409")) {
        setApiError("A customer with this phone or consumer number already exists.");
      } else {
        setApiError(err.message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Add Customer" onClose={onClose}>
      {apiError && <div className="form-error">{apiError}</div>}
      
      <p className="form-intro">Add the customer details available in your source record. Only a name and one contact identifier are required.</p>
      <div className="form-grid">
        <div className={errors.name ? "form-field-error" : ""}>
          <label>Customer Name *</label>
          <input name="name" value={formData.name} onChange={handleChange} placeholder="John Doe" />
          {errors.name && <div className="form-error">{errors.name}</div>}
        </div>
        <div className={errors.phone ? "form-field-error" : ""}>
          <label>Mobile Number</label>
          <input name="phone" value={formData.phone} onChange={handleChange} placeholder="9876543210" />
          {errors.phone && !errors.name && <div className="form-error">{errors.phone}</div>}
        </div>
      </div>
      
      <div className="form-grid">
        <div>
          <label>Email</label>
          <input name="email" value={formData.email} onChange={handleChange} placeholder="john@example.com" />
        </div>
        <div className={errors.consumer_number ? "form-field-error" : ""}>
          <label>Consumer Number</label>
          <input name="consumer_number" value={formData.consumer_number} onChange={handleChange} placeholder="Account or consumer ID" />
          {errors.consumer_number && <div className="form-error">{errors.consumer_number}</div>}
        </div>
      </div>

      <div className="form-grid">
        <div><label>Service</label><input name="service" value={formData.service} onChange={handleChange} placeholder="Service or product" /></div>
        <div><label>Address</label><input name="address" value={formData.address} onChange={handleChange} placeholder="Full address" /></div>
      </div>
      
      <div>
        <label>Notes</label>
        <textarea name="notes" value={formData.notes} onChange={handleChange} placeholder="Optional notes" />
      </div>

      <div className="modal-actions">
        <button className="button secondary" onClick={onClose} disabled={saving}>Cancel</button>
        <button className="button primary" onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving..." : "Add Customer"}
        </button>
      </div>
    </Modal>
  );
}

export default App;
