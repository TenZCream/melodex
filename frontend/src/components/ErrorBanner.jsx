import './ErrorBanner.css'

export default function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <p className="error-banner" role="alert">
      {message}
    </p>
  )
}
