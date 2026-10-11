import React from 'react';

export default function RetroField({
  label,
  id,
  type = 'text',
  value,
  onChange,
  placeholder = '',
  required = false,
  autoComplete,
  disabled = false,
  error = '',
  className = '',
  style = {}
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', width: '100%' }}>
      {label && (
        <label
          htmlFor={id}
          style={{
            fontFamily: "var(--font-body)",
            fontWeight: 700,
            fontSize: '13px',
            color: 'var(--ink)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em'
          }}
        >
          {label}
        </label>
      )}
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
        disabled={disabled}
        className={`fld ${className}`.trim()}
        style={style}
      />
      {error && (
        <span style={{ color: 'var(--red)', fontSize: '12px', fontWeight: 600 }}>
          {error}
        </span>
      )}
    </div>
  );
}
