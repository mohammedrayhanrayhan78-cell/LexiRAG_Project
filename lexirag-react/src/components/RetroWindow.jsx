import React from 'react';

export default function RetroWindow({
  title,
  variant = 'red', // 'red' | 'lilac' | 'amber'
  children,
  className = '',
  style = {},
  action = null
}) {
  const barClass = `bar ${variant === 'red' ? '' : variant}`.trim();
  return (
    <div className={`win ${className}`.trim()} style={style}>
      <div className={barClass}>
        <span>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {action}
          <span className="tbs" aria-hidden="true">
            <i className="tb" />
            <i className="tb" />
            <i className="tb" />
          </span>
        </div>
      </div>
      {children}
    </div>
  );
}
