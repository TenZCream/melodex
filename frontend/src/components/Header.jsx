import './Header.css'

export default function Header({ connection = 'pending', indexSize = null }) {
  const connected = connection === 'on' && indexSize != null

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <div className="site-header__brand">
          <h1>Melodex</h1>
          <p className="site-header__tagline">Hum it. Find it. Then find something new.</p>
        </div>
        <p className={`status${connected ? ' status--on' : ''}`} aria-live="polite">
          <span className="status__dot" aria-hidden="true" />
          {connected ? (
            `Connected · ${indexSize} melodies indexed`
          ) : (
            <span className="status__sr">
              {connection === 'pending' ? 'Checking the server' : 'Not connected'}
            </span>
          )}
        </p>
      </div>
    </header>
  )
}
