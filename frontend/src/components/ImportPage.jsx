import { useState } from "react";
import { FileSpreadsheet, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "../api";
import { StatusPill } from "./common/StatusPill";
import { EmptyState } from "./common/EmptyState";

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
    return (
      <EmptyState
        icon={FileSpreadsheet}
        title="No preview rows returned"
        text="The backend did not return preview records."
      />
    );
  }

  const rows = data.slice(0, 100);
  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row || {})))
  ).slice(0, 10);

  return (
    <div className="preview-table-wrap">
      <table>
        <thead>
          <tr>{columns.map((col) => <th key={col}>{col.replaceAll("_", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((col) => (
                <td key={col} title={String(row?.[col] ?? "")}>
                  {String(row?.[col] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ImportPage() {
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
    const valid = /\.(csv|xlsx)$/i.test(nextFile.name);
    if (!valid) {
      setMessage("Please select a CSV or XLSX file.");
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
        `Import completed: ${data.imported_rows ?? 0} imported, ` +
        `${data.duplicate_rows ?? 0} duplicates, ${data.skipped_rows ?? 0} skipped.`
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
          {/* File drop zone */}
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
                accept=".csv,.xlsx"
                onChange={(e) => chooseFile(e.target.files?.[0])}
              />
              <div className="import-icon"><FileSpreadsheet size={30} /></div>
              <strong>Drop your customer file here</strong>
              <span>or click to browse</span>
              <small>CSV or XLSX</small>
            </label>
          )}

          {/* Selected file */}
          {file && (
            <div className="selected-file">
              <div className="file-symbol"><FileSpreadsheet size={22} /></div>
              <div className="file-meta">
                <strong>{file.name}</strong>
                <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <button className="icon-button" onClick={reset} title="Remove file">
                <X size={17} />
              </button>
            </div>
          )}

          {/* Sheet selector */}
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
                {analysis.sheets.map((sheet) => (
                  <option key={sheet} value={sheet}>{sheet}</option>
                ))}
              </select>
              <span>Select the sheet containing customer records.</span>
            </div>
          )}

          {/* Analyze action */}
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

          {/* Analysis result */}
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
                <AnalysisStat label="Rows (sample)" value={analysis.total_rows ?? 0} />
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

          {/* Preview result */}
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
                <AnalysisStat label="Total rows" value={previewSummary.valid_records ?? preview.total_rows ?? "—"} />
                <AnalysisStat label="New records" value={previewSummary.new_records ?? "—"} />
                <AnalysisStat label="Already in DB" value={previewSummary.already_in_database ?? "—"} />
                <AnalysisStat label="Shown" value={(preview.preview || []).length} />
              </div>

              <PreviewTable data={preview.preview || []} />

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

          {/* Complete */}
          {step === "complete" && (
            <div className="import-complete">
              <div className="complete-icon"><CheckCircle2 size={28} /></div>
              <h3>Import completed</h3>
              <p>{message || "Your customer data was imported successfully."}</p>
              <button className="button secondary" onClick={reset}>Import another file</button>
            </div>
          )}

          {/* Error message */}
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
