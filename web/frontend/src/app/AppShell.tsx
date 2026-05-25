import { useEffect, useState, type ReactNode } from 'react'

type ThemeMode = 'day' | 'night'

export type AppShellProps = {
  children: ReactNode
  className?: string
  eyebrow?: ReactNode
  metric?: ReactNode
  subtitle?: ReactNode
  title: ReactNode
}

export function AppShell({
  children,
  className,
  eyebrow,
  metric,
  subtitle,
  title,
}: AppShellProps) {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const saved = window.localStorage.getItem('top10-theme-mode')
    if (saved === 'day' || saved === 'night') return saved
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'day' : 'night'
  })
  const classes = ['app-shell', className].filter(Boolean).join(' ')

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode
    window.localStorage.setItem('top10-theme-mode', themeMode)
  }, [themeMode])

  return (
    <main className={classes}>
      <section className="hero-panel">
        <div>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h1>{title}</h1>
          {subtitle ? <p className="hero-copy">{subtitle}</p> : null}
        </div>
        <div className="hero-actions">
          <div className="theme-switcher" role="group" aria-label="切換白天或夜晚模式">
            <button
              aria-pressed={themeMode === 'day'}
              className={themeMode === 'day' ? 'theme-switcher__button theme-switcher__button--active' : 'theme-switcher__button'}
              onClick={() => setThemeMode('day')}
              type="button"
            >
              白天
            </button>
            <button
              aria-pressed={themeMode === 'night'}
              className={themeMode === 'night' ? 'theme-switcher__button theme-switcher__button--active' : 'theme-switcher__button'}
              onClick={() => setThemeMode('night')}
              type="button"
            >
              夜晚
            </button>
          </div>
          {metric ? <div className="hero-stat">{metric}</div> : null}
        </div>
      </section>
      {children}
    </main>
  )
}
