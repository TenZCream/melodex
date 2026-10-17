import PlayButton from './PlayButton'
import './ResultsList.css'

export default function ResultsList({ results = [], indexSize, playingId, onPlay }) {
  return (
    <section className="results" aria-labelledby="results-heading">
      <div className="results__head">
        <h2 id="results-heading">Closest matches</h2>
        {indexSize ? <p>Among {indexSize} indexed melodies</p> : null}
      </div>
      {results.length === 0 ? (
        <p className="results__empty">No melodies came back close.</p>
      ) : (
        <ol className="results__list">
          {results.map((result) => {
            const pct = Math.max(0, Math.min(100, Math.round(result.score * 100)))
            return (
              <li key={result.id} className="result">
                <span className="result__rank">{result.rank}</span>
                <div className="result__title-row">
                  <p className="result__title">{result.title}</p>
                  <PlayButton
                    playing={playingId === result.id}
                    label={playingId === result.id ? `Stop ${result.title}` : `Play ${result.title}`}
                    onClick={() => onPlay?.(result)}
                  >
                    ▶ Play
                  </PlayButton>
                </div>
                <span className={`result__badge result__badge--${result.label}`}>{result.label}</span>
                <div className="result__sub">
                  <p className="result__composer">{result.composer}</p>
                  <div
                    className="result__meter"
                    role="meter"
                    aria-label="Similarity"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={pct}
                  >
                    <span style={{ width: `${pct}%` }} />
                  </div>
                  <span className="result__score">{result.score.toFixed(2)}</span>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
