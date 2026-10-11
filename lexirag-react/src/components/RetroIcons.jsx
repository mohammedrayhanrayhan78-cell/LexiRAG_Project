import React from 'react';

export function SparkleIcon({ size = 24, fill = '#FFF4E0', className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={{ pointerEvents: 'none', flexShrink: 0, ...style }}
    >
      <path
        d="M12 1 L14.2 9.8 L23 12 L14.2 14.2 L12 23 L9.8 14.2 L1 12 L9.8 9.8 Z"
        fill={fill}
        stroke="var(--ink, #3B1E17)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SmileyIcon({ size = 36, className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 40 40"
      className={className}
      style={{ pointerEvents: 'none', flexShrink: 0, ...style }}
    >
      <circle cx="20" cy="20" r="17" fill="var(--yellow, #F7C948)" stroke="var(--ink, #3B1E17)" strokeWidth="2" />
      <circle cx="14" cy="17" r="2" fill="var(--ink, #3B1E17)" />
      <circle cx="26" cy="17" r="2" fill="var(--ink, #3B1E17)" />
      <path
        d="M12 24 Q20 32 28 24"
        fill="none"
        stroke="var(--ink, #3B1E17)"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function BoltIcon({ size = 28, className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={{ flexShrink: 0, ...style }}
    >
      <path
        d="M13 2 L4 14 H11 L10 22 L20 9 H13 Z"
        fill="var(--yellow, #F7C948)"
        stroke="var(--ink, #3B1E17)"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function FolderIcon({ size = 24, className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 56 44"
      className={className}
      style={{ flexShrink: 0, ...style }}
    >
      <path
        d="M3 8 H20 L25 14 H53 V41 H3 Z"
        fill="var(--cream, #FCE8CC)"
        stroke="var(--ink, #3B1E17)"
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function WarningIcon({ size = 24, className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={{ flexShrink: 0, ...style }}
    >
      <path
        d="M12 2 L22 20 H2 Z"
        fill="var(--yellow, #F7C948)"
        stroke="var(--ink, #3B1E17)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <line x1="12" y1="9" x2="12" y2="14" stroke="var(--ink, #3B1E17)" strokeWidth="2" strokeLinecap="round" />
      <circle cx="12" cy="17" r="1.2" fill="var(--ink, #3B1E17)" />
    </svg>
  );
}

export function FileDocIcon({ size = 20, className = '', style = {} }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={{ flexShrink: 0, ...style }}
    >
      <path
        d="M14 2 H6 C4.9 2 4 2.9 4 4 V20 C4 21.1 4.9 22 6 22 H18 C19.1 22 20 21.1 20 20 V8 Z"
        fill="var(--cream-light, #FFF4E0)"
        stroke="var(--ink, #3B1E17)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M14 2 V8 H20" fill="none" stroke="var(--ink, #3B1E17)" strokeWidth="2" strokeLinejoin="round" />
      <line x1="8" y1="13" x2="16" y2="13" stroke="var(--ink, #3B1E17)" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="8" y1="17" x2="14" y2="17" stroke="var(--ink, #3B1E17)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
