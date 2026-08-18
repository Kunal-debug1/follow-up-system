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
import { EditCustomerModal } from "./components/EditCustomerModal";
import { CompleteFollowupModal } from "./components/CompleteFollowupModal";
import { ConfirmModal } from "./components/ConfirmModal";
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
  const [showArchived, setShowArchived] = useState(false);

  // Follow-up / dashboard state
  const [today, setToday] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [overdue, setOverdue] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);

  // Recent calls for Call History page
  const [recentCalls, setRecentCalls] = useState([]);

  // Customer detail state
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerCalls, setCustomerCalls] = useState([]);
  const [customerFollowups, setCustomerFollowups] = useState([]);
  const [timelineRefreshKey, setTimelineRefreshKey] = useState(0);

  // Modal state
  const [callModal, setCallModal] = useState(false);
  const [followupModal, setFollowupModal] = useState(false);
  const [customerModal, setCustomerModal] = useState(false);
  const [editCustomerModal, setEditCustomerModal] = useState(false);
  const [completeFollowupModal, setCompleteFollowupModal] = useState(false);
  const [followupToComplete, setFollowupToComplete] = useState(null);

  // Confirmation modals
  const [archiveConfirm, setArchiveConfirm] = useState(false);
  const [restoreConfirm, setRestoreConfirm] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Call form
  const [callStatus, setCallStatus] = useState("busy");
  const [callNotes, setCallNotes] = useState("");

  // Follow-up form
  const [followupDate, setFollowupDate] = useState("");
  const [followupTime, setFollowupTime] = useState("");
  const [followupReason, setFollowupReason] = useState("Customer busy");
  const [followupNotes, setFollowupNotes] = useState("");
  const [followupPriority, setFollowupPriority] = useState("medium");

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
    toastTimeoutRef.current = setTimeout(() => setToast(null), 3500);
  };

  const refreshTimeline = () => setTimelineRefreshKey((k) => k + 1);

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

  const loadRecentCalls = async () => {
    try {
      setLoading(true);
      const data = await api.recentCalls(50); // Get top 50 recent calls
      setRecentCalls(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadCustomers = async (searchTerm = "", p = 1, limit = pageLimit, archived = showArchived) => {
    customerRequestRef.current?.abort();
    const controller = new AbortController();
    customerRequestRef.current = controller;

    try {
      setLoading(true);
      const data = await api.customers({
        search: searchTerm,
        page: p,
        limit,
        archived,
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
    } else if (activePage === "calls") {
      loadRecentCalls();
    }
  }, [activePage, isAuthenticated]);

  // Debounced customer search (also re-fires when showArchived changes)
  useEffect(() => {
    if (!isAuthenticated) return;
    const timer = setTimeout(() => {
      loadCustomers(search, 1, pageLimit, showArchived);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, pageLimit, isAuthenticated, showArchived]);

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
    setEditCustomerModal(false);
    setArchiveConfirm(false);
    setRestoreConfirm(false);
    setDeleteConfirm(false);
  };

  const handleCustomerCreated = async () => {
    setCustomerModal(false);
    showToast("Customer created successfully");
    await loadCustomers(search, 1, pageLimit, showArchived);
    await loadOverview();
  };

  const handleCustomerEdited = async (updatedCustomer) => {
    setEditCustomerModal(false);
    setSelectedCustomer(updatedCustomer);
    showToast("Customer updated successfully");
    await loadCustomers(search, page, pageLimit, showArchived);
  };

  // Archive
  const handleArchiveConfirm = async () => {
    if (!selectedCustomer) return;
    try {
      setArchiveLoading(true);
      await api.archiveCustomer(selectedCustomer.id);
      setArchiveConfirm(false);
      closeCustomer();
      showToast(`${selectedCustomer.name} has been archived`);
      await loadCustomers(search, 1, pageLimit, showArchived);
      await loadOverview();
    } catch (err) {
      setError(err.message);
    } finally {
      setArchiveLoading(false);
    }
  };

  // Restore
  const handleRestoreConfirm = async () => {
    if (!selectedCustomer) return;
    try {
      setArchiveLoading(true);
      const restored = await api.restoreCustomer(selectedCustomer.id);
      setRestoreConfirm(false);
      setSelectedCustomer((prev) => ({ ...prev, is_archived: false, archived_at: null, archived_by: null }));
      showToast(`${selectedCustomer.name} has been restored`);
      await loadCustomers(search, 1, pageLimit, showArchived);
      await loadOverview();
    } catch (err) {
      setError(err.message);
    } finally {
      setArchiveLoading(false);
    }
  };

  // Permanent delete
  const handleDeleteConfirm = async () => {
    if (!selectedCustomer) return;
    try {
      setDeleteLoading(true);
      await api.deleteCustomerPermanently(selectedCustomer.id);
      setDeleteConfirm(false);
      closeCustomer();
      showToast(`${selectedCustomer.name} permanently deleted`, "error");
      await loadCustomers(search, 1, pageLimit, showArchived);
      await loadOverview();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  // Toggle archived view
  const handleToggleArchived = () => {
    setShowArchived((v) => !v);
    setSearch("");
    setPage(1);
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
      refreshTimeline();
      await loadOverview();
      showToast("Call logged successfully");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Called when WhatsApp button is clicked in CustomerDrawer
  const handleWhatsAppLogged = async () => {
    if (!selectedCustomer) return;
    try {
      const calls = await api.calls(selectedCustomer.id);
      setCustomerCalls(calls);
      refreshTimeline();
      await loadOverview();
    } catch {
      // Non-critical refresh — ignore failures silently
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
        priority: followupPriority,
      });
      const followups = await api.followups(selectedCustomer.id);
      setCustomerFollowups(followups);
      setFollowupModal(false);
      setFollowupDate("");
      setFollowupTime("");
      setFollowupNotes("");
      setFollowupPriority("medium");
      refreshTimeline();
      await loadOverview();
      showToast("Follow-up scheduled successfully");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Open the complete modal (accepts a followup object)
  const openCompleteFollowup = (followup) => {
    setFollowupToComplete(followup);
    setCompleteFollowupModal(true);
  };

  // Called from FollowupsPage or CustomerDrawer
  const handleCompleteFollowup = (followupOrId) => {
    // FollowupsPage and CustomerDrawer now pass the full followup object
    if (typeof followupOrId === "object" && followupOrId !== null) {
      openCompleteFollowup(followupOrId);
    } else {
      // Fallback: if only an ID was passed, build a minimal object
      openCompleteFollowup({ id: followupOrId });
    }
  };

  const handleCompleteFollowupSuccess = async (result) => {
    setCompleteFollowupModal(false);
    setFollowupToComplete(null);

    const msg = result.next_followup
      ? "Follow-up completed. Next follow-up scheduled."
      : "Follow-up marked as completed.";
    showToast(msg);

    // Refresh follow-ups and overview
    await loadOverview();
    if (selectedCustomer) {
      const followups = await api.followups(selectedCustomer.id);
      setCustomerFollowups(followups);
      refreshTimeline();
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
            onPageChange={(p) => loadCustomers(search, p, pageLimit, showArchived)}
            showArchived={showArchived}
            onToggleArchived={handleToggleArchived}
          />
        )}

        {activePage === "followups" && (
          <FollowupsPage
            overdue={overdue}
            today={today}
            upcoming={upcoming}
            onCustomer={openCustomer}
            onComplete={handleCompleteFollowup}
          />
        )}

        {activePage === "calls" && (
          <CallsPage calls={recentCalls} onCustomer={openCustomer} />
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
            onComplete={handleCompleteFollowup}
            onEdit={() => setEditCustomerModal(true)}
            onArchive={() => setArchiveConfirm(true)}
            onRestore={() => setRestoreConfirm(true)}
            onPermanentDelete={() => setDeleteConfirm(true)}
            timelineRefreshKey={timelineRefreshKey}
            onWhatsAppLogged={handleWhatsAppLogged}
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
            <label>Priority</label>
            <select
              value={followupPriority}
              onChange={(e) => setFollowupPriority(e.target.value)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
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

        {/* Edit customer modal */}
        {editCustomerModal && selectedCustomer && (
          <EditCustomerModal
            customer={selectedCustomer}
            onClose={() => setEditCustomerModal(false)}
            onSuccess={handleCustomerEdited}
          />
        )}

        {/* Complete follow-up modal */}
        {completeFollowupModal && followupToComplete && (
          <CompleteFollowupModal
            followup={followupToComplete}
            onClose={() => {
              setCompleteFollowupModal(false);
              setFollowupToComplete(null);
            }}
            onSuccess={handleCompleteFollowupSuccess}
          />
        )}

        {/* Archive confirmation */}
        {archiveConfirm && selectedCustomer && (
          <ConfirmModal
            title="Archive customer?"
            message={`Archive ${selectedCustomer.name}?`}
            subMessage="Customer data and history will be preserved. The customer can be restored at any time."
            confirmLabel="Archive"
            onConfirm={handleArchiveConfirm}
            onCancel={() => setArchiveConfirm(false)}
            loading={archiveLoading}
          />
        )}

        {/* Restore confirmation */}
        {restoreConfirm && selectedCustomer && (
          <ConfirmModal
            title="Restore customer?"
            message={`Restore ${selectedCustomer.name} to active status?`}
            subMessage="The customer will reappear in the active customer list."
            confirmLabel="Restore"
            onConfirm={handleRestoreConfirm}
            onCancel={() => setRestoreConfirm(false)}
            loading={archiveLoading}
          />
        )}

        {/* Permanent delete confirmation */}
        {deleteConfirm && selectedCustomer && (
          <ConfirmModal
            title="Permanently delete customer?"
            message={`Delete ${selectedCustomer.name} forever?`}
            subMessage="This permanently deletes the customer and ALL related calls and follow-ups. This action cannot be undone. Admin access required."
            confirmLabel="Delete Permanently"
            danger={true}
            onConfirm={handleDeleteConfirm}
            onCancel={() => setDeleteConfirm(false)}
            loading={deleteLoading}
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
