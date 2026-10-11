"""Train the full-match corner GBDT from finished matches already in the database.

Run from the engine directory (or anywhere; the path is fixed up below):

    .\\.venv\\Scripts\\python.exe scripts/train_corner_model.py

Features for each match are built only from earlier matches in the same league,
so the label is never leaked. The artifact is written to
``core-prediction-engine/models/corner_gbdt.json`` and picked up by the API on
its next start; if it is missing or corrupt the engine silently falls back to
the Poisson prior.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from sqlalchemy import select  # noqa: E402

from shared.corner_model import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    build_features,
    train_model,
    vector,
)
from shared.corners import project_corner_history  # noqa: E402
from shared.database import SessionLocal, init_db  # noqa: E402
from shared.models import Fixture  # noqa: E402


async def load_rows():
    async with SessionLocal() as session:
        result = await session.execute(
            select(Fixture)
            .where(Fixture.home_corners.is_not(None))
            .where(Fixture.away_corners.is_not(None))
            .order_by(Fixture.kickoff_at)
        )
        fixtures = list(result.scalars())
    return project_corner_history(fixtures)


def build_samples(rows) -> list[tuple[dict, float]]:
    ordered = sorted(rows, key=lambda r: (r.day, r.home_key, r.away_key))
    pool: dict[str, list] = defaultdict(list)
    samples: list[tuple[dict, float]] = []
    for target in ordered:
        prior = pool[target.league_key or ""]
        if prior:
            feats = build_features(
                prior,
                home_key=target.home_key,
                away_key=target.away_key,
                today=target.day,
                kickoff_day=target.day,
            )
            if feats is not None:
                samples.append((feats, float(target.home_corners + target.away_corners)))
        pool[target.league_key or ""].append(target)
    return samples


def evaluate(model, samples) -> float:
    total = 0.0
    for feats, label in samples:
        total += abs(model.predict(feats) - label)
    return total / len(samples) if samples else float("nan")


def baseline(samples) -> float:
    total = 0.0
    for feats, label in samples:
        total += abs(feats["expected_total"] - label)
    return total / len(samples) if samples else float("nan")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.06)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--min-leaf", type=int, default=25)
    parser.add_argument("--max-features", type=int, default=4)
    args = parser.parse_args()

    await init_db()
    rows = await load_rows()
    samples = build_samples(rows)
    print(f"finished corner rows: {len(rows)}   usable training samples: {len(samples)}")
    if len(samples) < 100:
        raise SystemExit("Not enough history to train a useful model.")

    split = int(len(samples) * 0.8)
    train, test = samples[:split], samples[split:]

    model = train_model(
        train,
        n_estimators=args.estimators,
        learning_rate=args.learning_rate,
        max_depth=args.depth,
        min_leaf=args.min_leaf,
        max_features=args.max_features,
        subsample=0.8,
        random_state=7,
    )
    test_mae = evaluate(model, test)
    base_mae = baseline(test)
    # Calibrate the over/under spread on the held-out set, not the (overfit) train set.
    model.residuals = sorted(label - model.predict(feats) for feats, label in test)
    model.metrics.update({"test_mae": round(test_mae, 4), "baseline_mae": round(base_mae, 4), "test_n": len(test)})
    print(f"train MAE: {model.metrics['mae']:.4f}")
    print(f"test  MAE: {test_mae:.4f}   (Poisson baseline: {base_mae:.4f})")
    print(f"dispersion: {model.dispersion}")

    model.save(args.out)
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
