import type { ElementType, HTMLAttributes, ReactNode } from 'react'

type PanelOwnProps<TElement extends ElementType> = {
  as?: TElement
  children: ReactNode
  className?: string
  eyebrow?: ReactNode
  footer?: ReactNode
  title?: ReactNode
}

export type PanelProps<TElement extends ElementType = 'section'> = PanelOwnProps<TElement> &
  Omit<HTMLAttributes<HTMLElement>, keyof PanelOwnProps<TElement>>

export function Panel<TElement extends ElementType = 'section'>({
  as,
  children,
  className,
  eyebrow,
  footer,
  title,
  ...panelProps
}: PanelProps<TElement>) {
  const Component = as ?? 'section'
  const classes = ['panel', className].filter(Boolean).join(' ')
  const hasHeader = Boolean(eyebrow || title)

  return (
    <Component className={classes} {...panelProps}>
      {hasHeader ? (
        <header className="panel__header">
          {eyebrow ? <p className="panel__eyebrow">{eyebrow}</p> : null}
          {title ? <h2 className="panel__title">{title}</h2> : null}
        </header>
      ) : null}
      <div className="panel__body">{children}</div>
      {footer ? <footer className="panel__footer">{footer}</footer> : null}
    </Component>
  )
}
