import React, { useCallback } from "react";

import ConfidenceBadge from "./ConfidenceBadge";

export interface ExtractionField {
  id: string;
  name: string;
  value: string;
  confidence: number;
}

interface FieldEditorProps {
  field: ExtractionField;
  onUpdate: (value: string) => void;
  onApprove: () => void;
  onLocate: () => void;
  isActive: boolean;
}

const FieldEditor: React.FC<FieldEditorProps> = ({
  field,
  onApprove,
  onLocate,
  onUpdate,
  isActive,
}) => {
  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onUpdate(event.target.value);
    },
    [onUpdate],
  );

  return (
    <div
      style={{
        border: isActive ? "2px solid #2563eb" : "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        backgroundColor: isActive ? "#eff6ff" : "#ffffff",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <div style={{ fontWeight: 600 }}>{field.name}</div>
        <ConfidenceBadge confidence={field.confidence} />
      </div>
      <input
        aria-label={`${field.name} value`}
        value={field.value}
        onChange={handleChange}
        style={{
          border: "1px solid #d1d5db",
          borderRadius: 6,
          padding: "6px 8px",
        }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={onLocate}
          style={{
            border: "1px solid #d1d5db",
            borderRadius: 6,
            padding: "6px 10px",
            backgroundColor: "#f9fafb",
            cursor: "pointer",
          }}
        >
          Locate
        </button>
        <button
          type="button"
          onClick={onApprove}
          style={{
            border: "1px solid #16a34a",
            borderRadius: 6,
            padding: "6px 10px",
            backgroundColor: "#16a34a",
            color: "#ffffff",
            cursor: "pointer",
          }}
        >
          Approve
        </button>
      </div>
    </div>
  );
};

export default FieldEditor;
