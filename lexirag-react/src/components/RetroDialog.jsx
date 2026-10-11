import React from 'react';
import RetroWindow from './RetroWindow';
import RetroButton from './RetroButton';
import { WarningIcon } from './RetroIcons';

export default function RetroDialog({
  isOpen,
  title = 'Confirm',
  message,
  confirmText = 'OK',
  cancelText = 'Cancel',
  danger = false,
  onConfirm,
  onCancel,
}) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(59, 30, 23, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
        backdropFilter: 'blur(2px)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <RetroWindow
        title={title}
        variant={danger ? 'red' : 'amber'}
        style={{ width: '100%', maxWidth: '420px', animation: 'retroPop 0.1s ease' }}
      >
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <WarningIcon size={32} />
            <div style={{ fontSize: '14px', lineHeight: '1.45', fontWeight: 500 }}>
              {message}
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '4px' }}>
            <RetroButton variant="alt" onClick={onCancel}>
              {cancelText}
            </RetroButton>
            <RetroButton variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>
              {confirmText}
            </RetroButton>
          </div>
        </div>
      </RetroWindow>
    </div>
  );
}
