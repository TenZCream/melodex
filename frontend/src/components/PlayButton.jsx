import './PlayButton.css'

export default function PlayButton({ playing = false, onClick, children, label }) {
  return (
    <button
      type="button"
      className={playing ? 'play-btn play-btn--on' : 'play-btn'}
      aria-pressed={playing}
      aria-label={label}
      onClick={onClick}
    >
      {playing ? '■ Stop' : children}
    </button>
  )
}
