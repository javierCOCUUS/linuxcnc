import { useState } from 'react'
import { PositionPanel } from './panels/PositionPanel'
import { ProgramPanel, CycleControls } from './panels/ProgramPanel'
import { OverridesPanel } from './panels/OverridesPanel'
import { SpindlePanel } from './panels/SpindlePanel'
import { JogControlPanel } from './panels/JogControlPanel'
import { MacrosPanel } from './panels/MacrosPanel'

function Card({ title, children, wide = false }: { title: string; children: JSX.Element; wide?: boolean }): JSX.Element {
  return (
    <section className={`op-card${wide ? ' op-card--wide' : ''}`} aria-label={title}>
      <h2 className="op-card-title">{title}</h2>
      {children}
    </section>
  )
}

// The everyday screen: one fixed page of cards instead of a free-form workspace, so the
// buttons used all day are always where the operator expects them.
export function OperationScreen(): JSX.Element {
  // The program is opened in one card and started from another, so the file is shared here.
  const [opened, setOpened] = useState<string | null>(null)
  return (
    <div className="op-screen">
      <div className="op-column">
        <Card title="Posición"><PositionPanel /></Card>
        <Card title="Programa"><ProgramPanel showCycle={false} opened={opened} onOpened={setOpened} /></Card>
        <Card title="Husillo"><SpindlePanel /></Card>
      </div>
      <div className="op-column">
        <Card title="Ciclo"><CycleControls openedFile={opened} /></Card>
        <Card title="Avance y spindle"><OverridesPanel /></Card>
        <Card title="Macros"><MacrosPanel /></Card>
      </div>
      <div className="op-column">
        <Card title="Jog"><JogControlPanel /></Card>
        <Card title="Herramienta y ceros">
          <div className="op-pending">
            Mandriles T1–T3, nuevos ceros y altura de herramienta: pendientes de traducir las macros de Mach3.
          </div>
        </Card>
      </div>
    </div>
  )
}
