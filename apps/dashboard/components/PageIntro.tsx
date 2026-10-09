type Props = {
  pending: number;
  placed: number;
};

export function PageIntro({ pending, placed }: Props) {
  return (
    <section className="page-intro">
      <h1>Over 1.5 football slips for BetPawa</h1>
      <p>Generate a slip of one to three teams priced 1.90–2.50, copy it, place manually, then mark when done.</p>
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
