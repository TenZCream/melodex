import './ModeToggle.css'

const TABS = [
  { id: 'hum', label: '🎤 Hum' },
  { id: 'keys', label: '🎹 Play keys' },
  { id: 'explore', label: '✨ Explore' },
]

export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode" role="tablist" aria-label="Melodex">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={mode === tab.id}
          aria-controls={`panel-${tab.id}`}
          className={mode === tab.id ? 'mode__option mode__option--on' : 'mode__option'}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
