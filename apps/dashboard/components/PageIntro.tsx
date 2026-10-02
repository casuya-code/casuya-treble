type Props = {
  pending: number;
  placed: number;
};

export function PageIntro({ pending, placed }: Props) {
  return (
    <section className="page-intro">
      <h1>Over 1.5 trebles for BetPawa</h1>
      <p>Generate a ≥3.00 acca, copy it, place manually, then mark when done.</p>
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
