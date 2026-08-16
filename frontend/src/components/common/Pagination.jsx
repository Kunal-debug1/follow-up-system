export function Pagination({
  page,
  totalPages,
  totalItems,
  limit,
  setLimit,
  onPageChange,
  itemsLength,
}) {
  const start = (page - 1) * limit + 1;
  const end = start + itemsLength - 1;

  return (
    <div className="pagination">
      <span>
        Showing {totalItems > 0 ? start : 0}–{end} of {totalItems} customers
      </span>
      <div className="pagination-controls">
        <select
          className="page-size-select"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        >
          <option value={25}>25 per page</option>
          <option value={50}>50 per page</option>
          <option value={100}>100 per page</option>
        </select>
        <button
          className="page-btn"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          {"<"}
        </button>
        <span style={{ padding: "0 8px" }}>
          Page {page} of {totalPages || 1}
        </span>
        <button
          className="page-btn"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          {">"}
        </button>
      </div>
    </div>
  );
}
