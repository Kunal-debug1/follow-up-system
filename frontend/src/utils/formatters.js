/** Shared formatting utilities. */

/**
 * Format an ISO date string (YYYY-MM-DD) for display.
 * @param {string|null} value
 * @returns {string}
 */
export function formatDate(value) {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * Display a phone number string, returning "—" for null/empty values.
 * @param {string|null|undefined} phone
 * @returns {string}
 */
export function displayPhone(phone) {
  if (phone === null || phone === undefined) return "—";
  const value = String(phone).trim();
  return value || "—";
}
