'use client';

import { cn } from '@/lib/utils';

/**
 * Mintlify-style secondary action button — outlined, subtle, used in
 * ExperienceManager and ProfileChunkEditor for inline edit controls.
 *
 * For icon-only usage (no label), provide ariaLabel for accessibility.
 */
export function MintButton({
  icon,
  label,
  onClick,
  danger,
  disabled,
  ariaLabel,
}: {
  icon: React.ReactNode;
  label?: string;
  onClick?: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** Required when no visible label is provided (icon-only mode) */
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-[10px] border transition-colors',
        'outline-none focus-visible:ring-2 [&_svg:not([class*="size-"])]:size-3.5',
        label
          ? 'gap-1.5 h-8 px-2.5 text-sm font-normal tracking-[-0.1px]'
          : 'size-8',
        danger
          ? 'text-text-secondary bg-surface-elevated border-border-subtle text-red-600 border-red-300 dark:border-red-800 hover:border-red-300 hover:bg-red-50 hover:text-error dark:hover:border-red-800 dark:hover:bg-red-950/20'
          : 'text-text-secondary bg-surface-elevated border-border-subtle hover:border-border-default hover:bg-surface-sunken hover:text-text-primary',
        disabled && 'opacity-40 cursor-not-allowed pointer-events-none',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
