import { cn } from "../../lib/utils";

interface LightRaysProps {
  /** Number of rays fanning out from the origin */
  count?: number;
  /** Total spread of the fan, in degrees */
  spread?: number;
  className?: string;
}

/**
 * God rays fanning down from the top of a section. Pure CSS gradients on
 * skewed elements — nothing paints per frame.
 */
export function LightRays({
  count = 9,
  spread = 70,
  className,
}: LightRaysProps) {
  return (
    <div
      aria-hidden
      data-slot="light-rays"
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden [mask-image:linear-gradient(to_bottom,black,transparent_80%)]",
        className
      )}
    >
      {Array.from({ length: count }).map((_, i) => {
        // Fan the rays evenly around vertical.
        const angle = -spread / 2 + (spread / (count - 1)) * i;
        return (
          <span
            key={i}
            style={{
              transform: `rotate(${angle}deg)`,
              opacity: 0.5 - Math.abs(angle) / (spread * 2.4),
            }}
            className="absolute -top-1/4 left-1/2 h-[150%] w-16 origin-top -translate-x-1/2 bg-[linear-gradient(to_bottom,var(--brand-via),transparent_70%)] blur-xl"
          />
        );
      })}
    </div>
  );
}
