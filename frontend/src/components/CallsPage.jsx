import { Phone, ChevronRight } from "lucide-react";

export function CallsPage({ customers, onCustomer }) {
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Activity</p>
          <h2>Call history</h2>
          <p>Open a customer to view their complete call history.</p>
        </div>
      </div>
      <div className="card">
        <div className="section-heading">
          <div>
            <h3>Customers with call activity</h3>
            <span>Select a customer to see calls and notes.</span>
          </div>
        </div>
        <div className="mini-list">
          {customers.slice(0, 50).map((customer) => (
            <button className="mini-row" key={customer.id} onClick={() => onCustomer(customer)}>
              <div className="avatar soft"><Phone size={17} /></div>
              <div className="mini-info">
                <strong>{customer.name}</strong>
                <span>{customer.phone || customer.consumer_number || "No contact detail"}</span>
              </div>
              <ChevronRight size={17} className="muted" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
