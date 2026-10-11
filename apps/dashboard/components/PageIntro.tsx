type Props = {
  pending: number;
  placed: number;
};

export function PageIntro({ pending, placed }: Props) {
  return (
    <section className="page-intro">
      <h1>Football slips for BetPawa</h1>
      <p>Generate a slip of one to four legs priced 1.30–6.00, copy it, place manually, then mark when done.</p>
      <div className="intro-stats">
        <span>
          <strong>{pending}</strong> pending
        </span>
        <span>
          <strong>{placed}</strong> placed
        </span>
      </div>
    </section>
  );
}
