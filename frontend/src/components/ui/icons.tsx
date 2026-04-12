/**
 * Custom SVG icons used across the dashboard.
 * Centralised here to avoid inline duplication.
 */

/** Filled circle checkmark — used in status/connected badges. */
export function IconCheck({ size = 10, className }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M9 1C4.589 1 1 4.589 1 9C1 13.411 4.589 17 9 17C13.411 17 17 13.411 17 9C17 4.589 13.411 1 9 1ZM12.843 6.708L8.593 12.208C8.457 12.384 8.25 12.491 8.028 12.499C8.018 12.499 8.009 12.499 8 12.499C7.788 12.499 7.585 12.409 7.442 12.251L5.192 9.751C4.915 9.443 4.94 8.969 5.248 8.691C5.557 8.415 6.029 8.439 6.308 8.747L7.956 10.579L11.657 5.79C11.91 5.462 12.382 5.402 12.709 5.655C13.037 5.908 13.097 6.379 12.844 6.707L12.843 6.708Z" />
    </svg>
  )
}

/** Tailoring/workflows icon — used in the sidebar and tailoring table rows. */
export function IconWorkflows({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M14.25 10.75H12.25C11.6977 10.75 11.25 11.1977 11.25 11.75V13.75C11.25 14.3023 11.6977 14.75 12.25 14.75H14.25C14.8023 14.75 15.25 14.3023 15.25 13.75V11.75C15.25 11.1977 14.8023 10.75 14.25 10.75Z" />
      <path d="M5.25 3.25H12.875C14.187 3.25 15.25 4.313 15.25 5.625C15.25 6.937 14.187 8 12.875 8H5.125C3.813 8 2.75 9.063 2.75 10.375C2.75 11.687 3.813 12.75 5.125 12.75H8.75" />
    </svg>
  )
}
