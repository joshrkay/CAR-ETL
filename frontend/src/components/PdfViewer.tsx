import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

export interface BoundingBox {
  id: string;
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PdfViewerProps {
  documentUrl: string;
  highlights: BoundingBox[];
  activeHighlight: string | null;
  onPageChange: (page: number) => void;
}

pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

const PdfViewer: React.FC<PdfViewerProps> = ({
  documentUrl,
  highlights,
  activeHighlight,
  onPageChange,
}) => {
  const [pageNumber, setPageNumber] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [scale, setScale] = useState(1.1);

  const pageHighlights = useMemo(
    () => highlights.filter((highlight) => highlight.page === pageNumber),
    [highlights, pageNumber],
  );

  useEffect(() => {
    if (!activeHighlight) {
      return;
    }
    const match = highlights.find((highlight) => highlight.id === activeHighlight);
    if (!match || match.page === pageNumber) {
      return;
    }
    setPageNumber(match.page);
    onPageChange(match.page);
  }, [activeHighlight, highlights, onPageChange, pageNumber]);

  const handleDocumentLoad = useCallback(
    ({ numPages: loadedPages }: { numPages: number }) => {
      setNumPages(loadedPages);
    },
    [],
  );

  const goToPage = useCallback(
    (nextPage: number) => {
      const clampedPage = Math.min(Math.max(nextPage, 1), numPages);
      setPageNumber(clampedPage);
      onPageChange(clampedPage);
    },
    [numPages, onPageChange],
  );

  const zoomIn = useCallback(() => {
    setScale((current) => Math.min(current + 0.1, 2));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((current) => Math.max(current - 0.1, 0.6));
  }, []);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: "1px solid #e5e7eb",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            onClick={() => goToPage(pageNumber - 1)}
            disabled={pageNumber <= 1}
          >
            Prev
          </button>
          <span>
            Page {pageNumber} of {numPages}
          </span>
          <button
            type="button"
            onClick={() => goToPage(pageNumber + 1)}
            disabled={pageNumber >= numPages}
          >
            Next
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button type="button" onClick={zoomOut}>
            -
          </button>
          <span>{Math.round(scale * 100)}%</span>
          <button type="button" onClick={zoomIn}>
            +
          </button>
        </div>
      </div>
      <div
        style={{
          flex: 1,
          overflow: "auto",
          backgroundColor: "#f1f5f9",
          display: "flex",
          justifyContent: "center",
        }}
      >
        <div style={{ position: "relative", padding: 16 }}>
          <Document file={documentUrl} onLoadSuccess={handleDocumentLoad}>
            <Page pageNumber={pageNumber} scale={scale} />
          </Document>
          {pageHighlights.map((highlight) => {
            const isActive = highlight.id === activeHighlight;
            return (
              <div
                key={highlight.id}
                style={{
                  position: "absolute",
                  left: `${highlight.x * 100}%`,
                  top: `${highlight.y * 100}%`,
                  width: `${highlight.width * 100}%`,
                  height: `${highlight.height * 100}%`,
                  border: `2px solid ${isActive ? "#2563eb" : "#f97316"}`,
                  backgroundColor: isActive
                    ? "rgba(37, 99, 235, 0.2)"
                    : "rgba(249, 115, 22, 0.15)",
                  pointerEvents: "none",
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
