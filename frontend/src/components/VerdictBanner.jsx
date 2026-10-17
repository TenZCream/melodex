import './VerdictBanner.css'

const LABELS = {
  strong: 'Strong match',
  possible: 'Possible match',
  none: 'No close match',
}

export default function VerdictBanner({ verdict, warnings = [] }) {
  if (!verdict) return null
  const label = LABELS[verdict.label] ?? verdict.label

  return (
    <section className={`verdict verdict--${verdict.label}`} aria-live="polite">
      <p className="verdict__label">{label}</p>
      <p className="verdict__message">{verdict.message}</p>
      {warnings.length > 0 ? (
        <ul className="verdict__warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
