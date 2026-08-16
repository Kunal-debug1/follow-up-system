import { ClipboardList } from "lucide-react";

export function EmptyState({ icon: Icon = ClipboardList, title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={22} /></div>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}
