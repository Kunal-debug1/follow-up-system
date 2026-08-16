import { useEffect, useRef, useState } from "react";
import {
  Bell,
  CalendarClock,
  FileSpreadsheet,
  LayoutDashboard,
  LogOut,
  Menu,
  Phone,
  Users,
  X,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { api } from "./api";

// Page components
import { LoginPage } from "./components/LoginPage";
import { Dashboard } from "./components/Dashboard";
import { CustomersPage } from "./components/CustomersPage";
import { FollowupsPage } from "./components/FollowupsPage";
import { CallsPage } from "./components/CallsPage";
import { ImportPage } from "./components/ImportPage";
import { CustomerDrawer } from "./components/CustomerDrawer";
import { CustomerFormModal } from "./components/CustomerFormModal";
import { Modal } from "./components/common/Modal";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

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

const EMPTY_STATS = {
  total_customers: 0,
  today_followups: 0,
  overdue_followups: 0,
  upcoming_followups: 0,
  calls_today: 0,
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  // Auth
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem("crm_token")
  );
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // Navigation
  const [activePage, setActivePage] = useState("dashboard");
  const [mobileNav, setMobileNav] = useState(false);

  // Customer list state
  const [customers, setCustomers] = useState([]);
  const [page, setPage] = useState(1);
  const [totalCustomers, setTotalCustomers] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [pageLimit, setPageLimit] = useState(50);
  const [search, setSearch] = useState("");

  // Follow-up / dashboard state
  const [today, setToday] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [overdue, setOverdue] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);

  // Customer detail state
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerCalls, setCustomerCalls] = useState([]);
  const [customerFollowups, setCustomerFollowups] = useState([]);

  // Modal state
  const [callModal, setCallModal] = useState(false);
  const [followupModal, setFollowupModal] = useState(false);
  const [customerModal, setCustomerModal] = useState(false);

  // Call form
  const [callStatus, setCallStatus] = useState("busy");
  const [callNotes, setCallNotes] = useState("");

  // Follow-up form
  const [followupDate, setFollowupDate] = useState("");
  const [followupTime, setFollowupTime] = useState("");
  const [followupReason, setFollowupReason] = useState("Customer busy");
  const [followupNotes, setFollowupNotes] = useState("");

  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);

  const customerRequestRef = useRef(null);
  const toastTimeoutRef = useRef(null);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const showToast = (message, type = "success") => {
    clearTimeout(toastTimeoutRef.current);
    setToast({ message, type });
    toastTimeoutRef.current = setTimeout(() => setToast(null), 3000);
  };

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  const loadOverview = async () => {
    try {
      setError("");
      const [todayData, upcomingData, overdueData, statsData] = await Promise.all([
        api.todayFollowups(),
        api.upcomingFollowups(7),
        api.overdueFollowups(),
        api.dashboardStats(),
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

  const loadCustomers = async (searchTerm = "", p = 1, limit = pageLimit) => {
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

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Cleanup on unmount
  useEffect(
    () => () => {
      customerRequestRef.current?.abort();
      clearTimeout(toastTimeoutRef.current);
    },
    []
  );

  // Load overview data when navigating to dashboard or followups
  useEffect(() => {
    if (!isAuthenticated) return;
    if (activePage === "dashboard" || activePage === "followups") {
      loadOverview();
    }
  }, [activePage, isAuthenticated]);

  // Debounced customer search
  useEffect(() => {
    if (!isAuthenticated) return;
    const timer = setTimeout(() => {
      loadCustomers(search, 1, pageLimit);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, pageLimit, isAuthenticated]);

  // ---------------------------------------------------------------------------
  // Auth handlers
  // ---------------------------------------------------------------------------

  const handleLogin = async (username, password) => {
    try {
      setLoginLoading(true);
      setLoginError("");
      const data = await api.login(username, password);
      localStorage.setItem("crm_token", data.token);
      localStorage.setItem("crm_user", data.username);
      setIsAuthenticated(true);
    } catch (err) {
      setLoginError(err.message || "Invalid credentials");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => api.logout();

  // ---------------------------------------------------------------------------
  // Customer handlers
  // ---------------------------------------------------------------------------

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

  const handleCustomerCreated = async () => {
    setCustomerModal(false);
    showToast("Customer created successfully");
    await loadCustomers(search, 1, pageLimit);
    await loadOverview();
  };

  // ---------------------------------------------------------------------------
  // Call handlers
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Follow-up handlers
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  const navigate = (id) => {
    setActivePage(id);
    setMobileNav(false);
    setSelectedCustomer(null);
  };

  const pageTitle = NAV.find((item) => item.id === activePage)?.label || "Dashboard";

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLogin={handleLogin}
        error={loginError}
        loading={loginLoading}
      />
    );
  }

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>CRM Follow-Up</strong>
            <span>Admin workspace</span>
          </div>
          <button className="mobile-close" onClick={() => setMobileNav(false)}>
            <X size={19} />
          </button>
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

      {mobileNav && (
        <div className="mobile-overlay" onClick={() => setMobileNav(false)} />
      )}

      {/* Main content */}
      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}>
            <Menu size={21} />
          </button>
          <div className="topbar-title">
            <span>Workspace</span>
            <h1>{pageTitle}</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" title="Notifications">
              <Bell size={19} />
            </button>
            <div className="top-avatar">A</div>
            <button className="icon-button" onClick={handleLogout} title="Logout">
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {error && (
          <div className="alert error">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={17} />
            </button>
          </div>
        )}

        {/* Pages */}
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

        {/* Customer detail drawer */}
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

        {/* Log call modal */}
        {callModal && (
          <Modal title="Log a call" onClose={() => setCallModal(false)}>
            <label>Call result</label>
            <select
              value={callStatus}
              onChange={(e) => setCallStatus(e.target.value)}
            >
              {CALL_STATUSES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <label>Notes</label>
            <textarea
              value={callNotes}
              onChange={(e) => setCallNotes(e.target.value)}
              placeholder="What happened on the call?"
            />
            <div className="modal-actions">
              <button
                className="button secondary"
                onClick={() => setCallModal(false)}
              >
                Cancel
              </button>
              <button
                className="button primary"
                onClick={saveCall}
                disabled={saving}
              >
                {saving ? "Saving..." : "Save call"}
              </button>
            </div>
          </Modal>
        )}

        {/* Schedule follow-up modal */}
        {followupModal && (
          <Modal
            title="Schedule follow-up"
            onClose={() => setFollowupModal(false)}
          >
            <div className="form-grid">
              <div>
                <label>Date</label>
                <input
                  type="date"
                  value={followupDate}
                  onChange={(e) => setFollowupDate(e.target.value)}
                />
              </div>
              <div>
                <label>Time</label>
                <input
                  type="time"
                  value={followupTime}
                  onChange={(e) => setFollowupTime(e.target.value)}
                />
              </div>
            </div>
            <label>Reason</label>
            <input
              value={followupReason}
              onChange={(e) => setFollowupReason(e.target.value)}
              placeholder="Customer busy"
            />
            <label>Notes</label>
            <textarea
              value={followupNotes}
              onChange={(e) => setFollowupNotes(e.target.value)}
              placeholder="Add a short note..."
            />
            <div className="modal-actions">
              <button
                className="button secondary"
                onClick={() => setFollowupModal(false)}
              >
                Cancel
              </button>
              <button
                className="button primary"
                onClick={saveFollowup}
                disabled={saving || !followupDate}
              >
                {saving ? "Saving..." : "Schedule follow-up"}
              </button>
            </div>
          </Modal>
        )}

        {/* Add customer modal */}
        {customerModal && (
          <CustomerFormModal
            onClose={() => setCustomerModal(false)}
            onSuccess={handleCustomerCreated}
          />
        )}
      </main>

      {/* Toast notifications */}
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>
            {toast.type === "success" ? (
              <CheckCircle2 size={18} />
            ) : (
              <AlertCircle size={18} />
            )}
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
