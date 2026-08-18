import { memo } from "react";
import { Phone, Plus, Search, ChevronRight, Archive } from "lucide-react";
import { EmptyState } from "./common/EmptyState";
import { StatusPill } from "./common/StatusPill";
import { Pagination } from "./common/Pagination";
import { displayPhone } from "../utils/formatters";

const PRIORITY_LABELS = { high: "High", medium: "Medium", low: "Low" };
const PRIORITY_CLASS = { high: "priority-high", medium: "priority-medium", low: "priority-low" };

const CustomerTable = memo(function CustomerTable({ customers, onCustomer }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Customer</th>
            <th>Phone</th>
            <th>Consumer no.</th>
            <th>Location</th>
            <th>Status</th>
            <th>Priority</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {customers.map((c) => (
            <tr key={c.id} className={c.is_archived ? "archived-row" : ""}>
              <td>
                <button className="customer-link" onClick={() => onCustomer(c)}>
                  <span className="avatar soft small">
                    {(c.name || "?").charAt(0).toUpperCase()}
                  </span>
                  <span>
                    <strong>{c.name}</strong>
                    <small>{c.email || "No email"}</small>
                  </span>
                </button>
              </td>
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
              <td>
                <span className={`priority-badge ${PRIORITY_CLASS[c.priority] || "priority-medium"}`}>
                  {PRIORITY_LABELS[c.priority] || "Medium"}
                </span>
              </td>
              <td>
                <button className="row-action" onClick={() => onCustomer(c)}>
                  <ChevronRight size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

export function CustomersPage({
  customers,
  search,
  setSearch,
  loading,
  onCustomer,
  onCreateCustomer,
  page,
  totalPages,
  totalCustomers,
  pageLimit,
  setPageLimit,
  onPageChange,
  showArchived,
  onToggleArchived,
}) {
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Customer database</p>
          <h2>{showArchived ? "Archived Customers" : "Customers"}</h2>
          <p>Search and open a customer to manage calls and follow-ups.</p>
        </div>
      </div>
      <div className="card">
        <div className="toolbar">
          <div className="search-box wide">
            <Search size={18} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, phone, consumer number, email…"
            />
          </div>

          {/* Archived toggle */}
          <button
            className={`button ${showArchived ? "primary" : "secondary"}`}
            onClick={onToggleArchived}
            title={showArchived ? "Show active customers" : "Show archived customers"}
          >
            <Archive size={15} />
            {showArchived ? "Active" : "Archived"}
          </button>

          {!showArchived && (
            <button className="button primary" onClick={onCreateCustomer}>
              <Plus size={16} /> Add Customer
            </button>
          )}
        </div>

        {loading && customers.length === 0 ? (
          <div className="loading">Loading customers…</div>
        ) : customers.length === 0 ? (
          <EmptyState
            icon={showArchived ? Archive : Search}
            title={showArchived ? "No archived customers" : "No customers found"}
            text={showArchived ? "No customers have been archived." : "Try a different search."}
          />
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
