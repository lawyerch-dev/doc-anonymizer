"use client";

import { useRef } from "react";

import { cn } from "../../lib/utils";

interface ThemeTogglerProps {
  /** Current theme; drives the icon and the accessible label */
  isDark: boolean;
  /** Apply the theme change. Called inside a View Transition when supported. */
  onToggle: () => void;
  className?: string;
}

/**
 * Light/dark switch that wipes the new theme in as an expanding circle from
 * the button itself, using the View Transitions API where it exists and
 * falling back to a plain toggle everywhere else.
 */
export function ThemeToggler({
  isDark,
  onToggle,
  className,
}: ThemeTogglerProps) {
  const ref = useRef<HTMLButtonElement>(null);

  const handleClick = async () => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const startViewTransition = document.startViewTransition?.bind(document);

    if (!startViewTransition || reduced) {
      onToggle();
      return;
    }

    const rect = ref.current?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
    // Radius that reaches the furthest corner of the viewport.
    const radius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y)
    );

    await startViewTransition(onToggle).ready;

    document.documentElement.animate(
      {
        clipPath: [
          `circle(0px at ${x}px ${y}px)`,
          `circle(${radius}px at ${x}px ${y}px)`,
        ],
      },
      {
        duration: 480,
        easing: "ease-in-out",
        pseudoElement: "::view-transition-new(root)",
      }
    );
  };

  return (
    <button
      ref={ref}
      type="button"
      data-slot="theme-toggler"
      onClick={handleClick}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className={cn(
        "grid size-9 cursor-pointer place-items-center rounded-lg border bg-background transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className
      )}
    >
      <svg
        width="17"
        height="17"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {isDark ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </>
        ) : (
          <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
        )}
      </svg>
    </button>
  );
}
