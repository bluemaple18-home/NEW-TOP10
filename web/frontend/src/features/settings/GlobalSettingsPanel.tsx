import { Panel } from '../../components'
import type {
  EntryPreference,
  GlobalInvestmentSettings,
  HoldingPeriod,
  RiskLimit,
  RiskStyle,
  TargetType,
} from '../weekly-candidates/candidateModel'
import {
  entryPreferenceLabel,
  holdingPeriodLabel,
  riskLimitLabel,
  riskStyleLabel,
  targetTypeLabel,
} from '../weekly-candidates/candidateModel'

type GlobalSettingsPanelProps = {
  settings: GlobalInvestmentSettings
  onChange: (settings: GlobalInvestmentSettings) => void
}

const riskStyles: RiskStyle[] = ['conservative', 'balanced', 'aggressive']
const targetTypes: TargetType[] = ['stocks', 'etfs', 'both']
const holdingPeriods: HoldingPeriod[] = ['swing', 'midterm', 'longterm']
const entryPreferences: EntryPreference[] = ['breakout', 'pullback', 'continuation', 'mixed']
const riskLimits: RiskLimit[] = ['lowVolatility', 'excludeThemes', 'acceptHighVolatility']

export function GlobalSettingsPanel({ onChange, settings }: GlobalSettingsPanelProps) {
  const update = <TKey extends keyof GlobalInvestmentSettings>(key: TKey, value: GlobalInvestmentSettings[TKey]) => {
    onChange({ ...settings, [key]: value })
  }

  return (
    <Panel as="aside" className="settings-panel" eyebrow="Global Settings" title="全域投資設定">
      <SettingGroup
        label="風險風格"
        options={riskStyles}
        renderLabel={riskStyleLabel}
        value={settings.riskStyle}
        onChange={(value) => update('riskStyle', value)}
      />
      <SettingGroup
        label="標的類型"
        options={targetTypes}
        renderLabel={targetTypeLabel}
        value={settings.targetType}
        onChange={(value) => update('targetType', value)}
      />
      <SettingGroup
        label="持有週期"
        options={holdingPeriods}
        renderLabel={holdingPeriodLabel}
        value={settings.holdingPeriod}
        onChange={(value) => update('holdingPeriod', value)}
      />
      <SettingGroup
        label="進場偏好"
        options={entryPreferences}
        renderLabel={entryPreferenceLabel}
        value={settings.entryPreference}
        onChange={(value) => update('entryPreference', value)}
      />
      <SettingGroup
        label="風險限制"
        options={riskLimits}
        renderLabel={riskLimitLabel}
        value={settings.riskLimit}
        onChange={(value) => update('riskLimit', value)}
      />
    </Panel>
  )
}

function SettingGroup<TValue extends string>({
  label,
  onChange,
  options,
  renderLabel,
  value,
}: {
  label: string
  options: TValue[]
  value: TValue
  renderLabel: (value: TValue) => string
  onChange: (value: TValue) => void
}) {
  return (
    <fieldset className="setting-group">
      <legend>{label}</legend>
      <div className="segmented-control">
        {options.map((option) => (
          <button
            aria-pressed={option === value}
            className={option === value ? 'segmented-control__item segmented-control__item--active' : 'segmented-control__item'}
            key={option}
            onClick={() => onChange(option)}
            type="button"
          >
            {renderLabel(option)}
          </button>
        ))}
      </div>
    </fieldset>
  )
}
