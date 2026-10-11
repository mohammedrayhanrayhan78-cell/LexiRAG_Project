import React from 'react';

export default function RetroButton({
  children,
  variant = 'primary', // 'primary' | 'alt' | 'danger'
  type = 'button',
  size = 'md', // 'md' | 'sm'
  onClick,
  disabled = false,
  className = '',
  style = {},
  ariaLabel
}) {
  const variantClass = variant === 'alt' ? 'alt' : variant === 'danger' ? 'danger' : '';
  const sizeClass = size === 'sm' ? 'sm' : '';
  const classes = `btn ${variantClass} ${sizeClass} ${className}`.trim();

  return (
    <button
      type={type}
      className={classes}
      onClick={onClick}
      disabled={disabled}
      style={style}
      aria-label={ariaLabel}
    >
      {children}
    </button>
  );
}
