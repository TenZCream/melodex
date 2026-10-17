import './ModeToggle.css'

export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode" role="tablist" aria-label="How to enter a melody">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'hum'}
        className={mode === 'hum' ? 'mode__option mode__option--on' : 'mode__option'}
        onClick={() => onChange('hum')}
      >
        Hum
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'keys'}
        className={mode === 'keys' ? 'mode__option mode__option--on' : 'mode__option'}
        onClick={() => onChange('keys')}
      >
        Play keys
      </button>
    </div>
  )
}
