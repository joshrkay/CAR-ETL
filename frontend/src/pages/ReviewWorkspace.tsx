import React, { useCallback, useEffect, useMemo, useState } from "react";

import ExtractionPanel from "../components/ExtractionPanel";
import PdfViewer from "../components/PdfViewer";
import { useReviewWorkspace } from "../hooks/useReviewWorkspace";

interface ReviewWorkspaceProps {
  documentId: string;
}

const ReviewWorkspace: React.FC<ReviewWorkspaceProps> = ({ documentId }) => {
  const {
    extraction,
    activeField,
    setActiveField,
    updateField,
    approveField,
    approveAll,
    submitReview,
    lastError,
  } = useReviewWorkspace(documentId);
  const [currentPage, setCurrentPage] = useState(1);

  const fields = extraction?.fields ?? [];
  const totalFields = fields.length;

  const activeIndex = useMemo(() => {
    if (!activeField) {
      return -1;
    }
    return fields.findIndex((field) => field.id === activeField);
  }, [activeField, fields]);

  const reviewLabel = useMemo(() => {
    if (activeIndex === -1) {
      return "Review";
    }
    return `Review ${activeIndex + 1} of ${totalFields}`;
  }, [activeIndex, totalFields]);

  const goToField = useCallback(
    (index: number) => {
      if (index < 0 || index >= fields.length) {
        return;
      }
      setActiveField(fields[index].id);
    },
    [fields, setActiveField],
  );

  const handleLocateField = useCallback(
    (fieldId: string) => {
      setActiveField(fieldId);
    },
    [setActiveField],
  );

  const handleExitReview = useCallback(() => {
    window.history.back();
  }, []);

  const handleApproveAll = useCallback(async () => {
    await approveAll();
    await submitReview();
  }, [approveAll, submitReview]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Tab") {
        event.preventDefault();
        if (event.shiftKey) {
          goToField(activeIndex - 1);
        } else {
          goToField(activeIndex + 1);
        }
      }

      if (event.key === "Enter" && event.ctrlKey) {
        event.preventDefault();
        void handleApproveAll();
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (activeField) {
          approveField(activeField);
        }
      }

      if (event.key === "Escape") {
        event.preventDefault();
        handleExitReview();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activeField,
    activeIndex,
    approveField,
    goToField,
    handleApproveAll,
    handleExitReview,
  ]);

  if (!extraction) {
    return <div style={{ padding: 24 }}>Loading review workspace...</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: "1px solid #e5e7eb",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button type="button" onClick={handleExitReview}>
            Back
          </button>
          <div>
            <div style={{ fontWeight: 600 }}>{extraction.documentName}</div>
            <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
              {reviewLabel}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button type="button" onClick={() => void approveAll()}>
            Approve all
          </button>
          <button type="button" onClick={() => void submitReview()}>
            Complete review
          </button>
        </div>
      </header>
      <main style={{ flex: 1, display: "flex" }}>
        <section style={{ flex: 1, borderRight: "1px solid #e5e7eb" }}>
          <PdfViewer
            documentUrl={extraction.documentUrl}
            highlights={extraction.highlights}
            activeHighlight={activeField}
            onPageChange={setCurrentPage}
          />
        </section>
        <section style={{ flex: 1 }}>
          <ExtractionPanel
            fields={fields}
            activeFieldId={activeField}
            onApproveField={approveField}
            onLocateField={handleLocateField}
            onUpdateField={updateField}
          />
        </section>
      </main>
      <footer
        style={{
          borderTop: "1px solid #e5e7eb",
          padding: "8px 16px",
          fontSize: "0.85rem",
          color: "#64748b",
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <span>Viewing page {currentPage}</span>
        {lastError ? <span>Last error: {lastError}</span> : null}
      </footer>
    </div>
  );
};

export default ReviewWorkspace;
