import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BoundingBox } from "../components/PdfViewer";
import { ExtractionField } from "../components/FieldEditor";

export interface Extraction {
  documentId: string;
  documentName: string;
  documentUrl: string;
  fields: ExtractionField[];
  highlights: BoundingBox[];
}

interface FieldUpdate {
  id: string;
  value: string;
}

interface RedactionResponse {
  updates: FieldUpdate[];
}

interface ReviewWorkspaceState {
  extraction: Extraction | null;
  pendingChanges: Map<string, string>;
  activeField: string | null;
  updateField: (fieldId: string, value: string) => void;
  approveField: (fieldId: string) => void;
  approveAll: () => Promise<void>;
  submitReview: () => Promise<void>;
  setActiveField: (fieldId: string) => void;
  hasUnsavedChanges: boolean;
  lastError: string | null;
}

const isFieldUpdate = (value: unknown): value is FieldUpdate => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const update = value as FieldUpdate;
  return typeof update.id === "string" && typeof update.value === "string";
};

const isRedactionResponse = (value: unknown): value is RedactionResponse => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const response = value as RedactionResponse;
  return Array.isArray(response.updates) && response.updates.every(isFieldUpdate);
};

const isExtractionField = (value: unknown): value is ExtractionField => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const field = value as ExtractionField;
  return (
    typeof field.id === "string" &&
    typeof field.name === "string" &&
    typeof field.value === "string" &&
    typeof field.confidence === "number"
  );
};

const isBoundingBox = (value: unknown): value is BoundingBox => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const highlight = value as BoundingBox;
  return (
    typeof highlight.id === "string" &&
    typeof highlight.page === "number" &&
    typeof highlight.x === "number" &&
    typeof highlight.y === "number" &&
    typeof highlight.width === "number" &&
    typeof highlight.height === "number"
  );
};

const isExtraction = (value: unknown): value is Extraction => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const extraction = value as Extraction;
  return (
    typeof extraction.documentId === "string" &&
    typeof extraction.documentName === "string" &&
    typeof extraction.documentUrl === "string" &&
    Array.isArray(extraction.fields) &&
    extraction.fields.every(isExtractionField) &&
    Array.isArray(extraction.highlights) &&
    extraction.highlights.every(isBoundingBox)
  );
};

const AUTOSAVE_DELAY_MS = 2000;
const PERIODIC_SAVE_MS = 30000;

export const useReviewWorkspace = (documentId: string): ReviewWorkspaceState => {
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Map<string, string>>(
    () => new Map(),
  );
  const [activeField, setActiveField] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const autosaveTimeout = useRef<number | null>(null);
  const periodicSave = useRef<number | null>(null);

  const hasUnsavedChanges = pendingChanges.size > 0;

  const recordError = useCallback(
    (message: string, context: Record<string, string>) => {
      console.error(message, context);
      setLastError(message);
    },
    [],
  );

  const assertResponseOk = useCallback((response: Response, action: string) => {
    if (!response.ok) {
      throw new Error(`${action} failed with status ${response.status}`);
    }
  }, []);

  const redactUpdates = useCallback(
    async (updates: FieldUpdate[]): Promise<FieldUpdate[]> => {
      if (!extraction) {
        return updates;
      }
      const response = await fetch(`/api/redaction/presidio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documentId: extraction.documentId,
          updates,
        }),
      });
      assertResponseOk(response, "Redaction");
      const data: unknown = await response.json();
      if (!isRedactionResponse(data)) {
        throw new Error("Invalid redaction payload");
      }
      return data.updates;
    },
    [assertResponseOk, extraction],
  );

  const saveChanges = useCallback(async () => {
    if (!extraction || pendingChanges.size === 0) {
      return;
    }

    try {
      const updates = Array.from(pendingChanges.entries()).map(([id, value]) => ({
        id,
        value,
      }));
      const redactedUpdates = await redactUpdates(updates);
      const response = await fetch(`/api/review/${extraction.documentId}/autosave`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documentId: extraction.documentId,
          updates: redactedUpdates,
        }),
      });
      assertResponseOk(response, "Autosave");
      setPendingChanges(new Map());
    } catch (error) {
      recordError("Review autosave failed", {
        documentId: extraction.documentId,
        operation: "autosave",
      });
    }
  }, [assertResponseOk, extraction, pendingChanges, recordError, redactUpdates]);

  const scheduleAutosave = useCallback(() => {
    if (autosaveTimeout.current) {
      window.clearTimeout(autosaveTimeout.current);
    }
    autosaveTimeout.current = window.setTimeout(() => {
      void saveChanges();
    }, AUTOSAVE_DELAY_MS);
  }, [saveChanges]);

  const updateField = useCallback(
    (fieldId: string, value: string) => {
      setExtraction((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          fields: current.fields.map((field) =>
            field.id === fieldId ? { ...field, value } : field,
          ),
        };
      });
      setPendingChanges((current) => {
        const updated = new Map(current);
        updated.set(fieldId, value);
        return updated;
      });
      scheduleAutosave();
    },
    [scheduleAutosave],
  );

  const approveField = useCallback(
    (fieldId: string) => {
      if (!extraction) {
        return;
      }
      const approve = async () => {
        const response = await fetch(`/api/review/${extraction.documentId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ documentId: extraction.documentId, fieldId }),
        });
        assertResponseOk(response, "Approve field");
      };
      void approve().catch((error) => {
        recordError("Approve field failed", {
          documentId: extraction.documentId,
          fieldId,
          operation: "approveField",
        });
      });
    },
    [assertResponseOk, extraction, recordError],
  );

  const approveAll = useCallback(async () => {
    if (!extraction) {
      return;
    }
    try {
      const response = await fetch(`/api/review/${extraction.documentId}/approve-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ documentId: extraction.documentId }),
      });
      assertResponseOk(response, "Approve all");
    } catch (error) {
      recordError("Approve all failed", {
        documentId: extraction.documentId,
        operation: "approveAll",
      });
    }
  }, [assertResponseOk, extraction, recordError]);

  const submitReview = useCallback(async () => {
    if (!extraction) {
      return;
    }
    try {
      const response = await fetch(`/api/review/${extraction.documentId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ documentId: extraction.documentId }),
      });
      assertResponseOk(response, "Submit review");
    } catch (error) {
      recordError("Submit review failed", {
        documentId: extraction.documentId,
        operation: "submitReview",
      });
    }
  }, [assertResponseOk, extraction, recordError]);

  useEffect(() => {
    const loadExtraction = async () => {
      try {
        const response = await fetch(`/api/review/${documentId}`);
        assertResponseOk(response, "Load extraction");
        const data: unknown = await response.json();
        if (isExtraction(data)) {
          setExtraction(data);
          setActiveField(data.fields[0]?.id ?? null);
        } else {
          recordError("Invalid extraction payload", {
            documentId,
            operation: "loadExtraction",
          });
        }
      } catch (error) {
        recordError("Failed to load extraction", {
          documentId,
          operation: "loadExtraction",
        });
      }
    };

    void loadExtraction();
  }, [documentId]);

  useEffect(() => {
    periodicSave.current = window.setInterval(() => {
      void saveChanges();
    }, PERIODIC_SAVE_MS);

    return () => {
      if (periodicSave.current) {
        window.clearInterval(periodicSave.current);
      }
    };
  }, [saveChanges]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  return useMemo(
    () => ({
      extraction,
      pendingChanges,
      activeField,
      updateField,
      approveField,
      approveAll,
      submitReview,
      setActiveField,
      hasUnsavedChanges,
      lastError,
    }),
    [
      extraction,
      pendingChanges,
      activeField,
      updateField,
      approveField,
      approveAll,
      submitReview,
      setActiveField,
      hasUnsavedChanges,
      lastError,
    ],
  );
};
