import React from "react";

import FieldEditor, { ExtractionField } from "./FieldEditor";

interface ExtractionPanelProps {
  fields: ExtractionField[];
  activeFieldId: string | null;
  onUpdateField: (fieldId: string, value: string) => void;
  onApproveField: (fieldId: string) => void;
  onLocateField: (fieldId: string) => void;
}

const ExtractionPanel: React.FC<ExtractionPanelProps> = ({
  fields,
  activeFieldId,
  onApproveField,
  onLocateField,
  onUpdateField,
}) => {
  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        backgroundColor: "#f8fafc",
      }}
    >
      {fields.map((field) => (
        <FieldEditor
          key={field.id}
          field={field}
          isActive={field.id === activeFieldId}
          onApprove={() => onApproveField(field.id)}
          onLocate={() => onLocateField(field.id)}
          onUpdate={(value) => onUpdateField(field.id, value)}
        />
      ))}
    </div>
  );
};

export default ExtractionPanel;
