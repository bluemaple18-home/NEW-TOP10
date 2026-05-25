import type { ReactNode } from 'react'

export type DetailSectionProps = {
  actions?: ReactNode
  children: ReactNode
  className?: string
  eyebrow?: ReactNode
  title: ReactNode
}

export function DetailSection({ actions, children, className, eyebrow, title }: DetailSectionProps) {
  const classes = ['detail-section', className].filter(Boolean).join(' ')

  return (
    <section className={classes}>
      <header className="detail-section__header">
        <div>
          {eyebrow ? <p className="detail-section__eyebrow">{eyebrow}</p> : null}
          <h3>{title}</h3>
        </div>
        {actions ? <div className="detail-section__actions">{actions}</div> : null}
      </header>
      <div className="detail-section__body">{children}</div>
    </section>
  )
}
