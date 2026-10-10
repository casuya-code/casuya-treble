/**
 * First-paint shells for the data routes.
 *
 * Every route under this app was a client component with no `loading.tsx`, so a
 * navigation painted nothing at all until the JS bundle booted, AuthGuard ran
 * its localStorage check, and the page's own fetches resolved. These skeletons
 * give the router something to render immediately, which is what actually moves
 * the perceived load time — the data still arrives on its own schedule.
 *
 * They are deliberately markup-free (no spinner component, no data): the point
 * is bytes on screen in the first response, not a faithful preview.
 */

function Bars({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="route-skeleton-bar" aria-hidden="true" />
      ))}
    </>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="route-skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="route-skeleton-visually-hidden">Loading…</span>
      {children}
    </div>
  );
}

/** Desk: header strip, controls, then the slip grid. */
export function DeskSkeleton() {
  return (
    <Frame>
      <div className="route-skeleton-title" aria-hidden="true" />
      <Bars count={2} />
      <Bars count={6} />
    </Frame>
  );
}

/** Admin and Hoops: a title and a dense table. */
export function TableSkeleton() {
  return (
    <Frame>
      <div className="route-skeleton-title" aria-hidden="true" />
      <Bars count={8} />
    </Frame>
  );
}
