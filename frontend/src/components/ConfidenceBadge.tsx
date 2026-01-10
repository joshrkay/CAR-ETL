import React from "react";

type ConfidenceLevel = "high" | "medium" | "low";

interface ConfidenceBadgeProps {
  confidence: number;
}

const getConfidenceLevel = (confidence: number): ConfidenceLevel => {
  if (confidence >= 0.85) {
    return "high";
  }
  if (confidence >= 0.6) {
    return "medium";
  }
  return "low";
};

const CONFIDENCE_COLORS: Record<ConfidenceLevel, string> = {
  high: "#16a34a",
  medium: "#ca8a04",
  low: "#dc2626",
};

const CONFIDENCE_BACKGROUNDS: Record<ConfidenceLevel, string> = {
  high: "#dcfce7",
  medium: "#fef9c3",
  low: "#fee2e2",
};

const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence }) => {
  const level = getConfidenceLevel(confidence);

  return (
    <span
      style={{
        backgroundColor: CONFIDENCE_BACKGROUNDS[level],
        borderRadius: "999px",
        color: CONFIDENCE_COLORS[level],
        display: "inline-flex",
        fontSize: "0.75rem",
        fontWeight: 600,
        padding: "2px 8px",
        textTransform: "uppercase",
      }}
    >
      {Math.round(confidence * 100)}%
    </span>
  );
};

export default ConfidenceBadge;
