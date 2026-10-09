export function TrebleSchematic() {
  return (
    <figure className="schematic">
      <svg className="pitch-svg" viewBox="0 0 280 400" role="img" aria-label="Football pitch with a ball moving through two match marks">
        <rect x="8" y="8" width="264" height="384" rx="18" fill="#178a4b" />
        <g className="pitch-lines" fill="none" stroke="#ffffff" strokeWidth="2.25">
          <rect className="pitch-line" x="28" y="24" width="224" height="352" rx="6" />
          <path className="pitch-line pitch-line-2" d="M28 200 H252" />
          <circle className="pitch-line pitch-line-3" cx="140" cy="200" r="42" />
          <circle cx="140" cy="200" r="3" fill="#ffffff" stroke="none" />
          <rect className="pitch-line pitch-line-4" x="78" y="24" width="124" height="62" />
          <rect className="pitch-line pitch-line-4" x="78" y="314" width="124" height="62" />
          <rect className="pitch-line pitch-line-5" x="104" y="24" width="72" height="28" />
          <rect className="pitch-line pitch-line-5" x="104" y="348" width="72" height="28" />
        </g>
        <g className="match-marks">
          <circle className="m1" cx="92" cy="120" r="8" />
          <circle className="m2" cx="188" cy="168" r="8" />
        </g>
        <circle className="pitch-ball" cx="0" cy="0" r="7" fill="#ffffff" stroke="#1d4ed8" strokeWidth="2.5" />
      </svg>

      <div className="schematic-side">
        <p className="schematic-kicker">Example slip</p>
        <ol className="leg-list">
          <li className="tone-blue">
            <span>Leg 1</span>
            <strong>Over 1.5</strong>
            <em>1.48</em>
          </li>
          <li className="tone-green">
            <span>Leg 2</span>
            <strong>Over 1.5</strong>
            <em>1.62</em>
          </li>
        </ol>
        <p className="treble-math" aria-label="1.48 times 1.62 equals 2.40">
          <span>1.48</span>
          <span className="times">×</span>
          <span>1.62</span>
          <span className="treble-eq">2.40</span>
        </p>
        <p className="schematic-caption">
          Example prices. Casuya Treble uses today’s BetPawa Over 1.5 odds, and only keeps a slip when the price lands between 2.10 and 2.50.
        </p>
      </div>
    </figure>
  );
}
