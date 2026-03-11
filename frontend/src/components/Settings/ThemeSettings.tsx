import { useThemeStore } from '../../store/themeStore';
import './ThemeSettings.css';

const ACCENT_PRESETS = [
  { label: 'Indigo', hex: '#6366f1' },
  { label: 'Violet', hex: '#8b5cf6' },
  { label: 'Rose', hex: '#e11d48' },
  { label: 'Amber', hex: '#f59e0b' },
  { label: 'Emerald', hex: '#10b981' },
  { label: 'Cyan', hex: '#06b6d4' },
  { label: 'Blue', hex: '#3b82f6' },
  { label: 'Fuchsia', hex: '#d946ef' },
];

const SUCCESS_PRESETS = ['#22c55e', '#10b981', '#14b8a6', '#84cc16'];
const ERROR_PRESETS = ['#ef4444', '#e11d48', '#f97316', '#dc2626'];

export function ThemeSettings() {
  const accentColor = useThemeStore((s) => s.accentColor);
  const successColor = useThemeStore((s) => s.successColor);
  const errorColor = useThemeStore((s) => s.errorColor);
  const setAccentColor = useThemeStore((s) => s.setAccentColor);
  const setSuccessColor = useThemeStore((s) => s.setSuccessColor);
  const setErrorColor = useThemeStore((s) => s.setErrorColor);
  const resetToDefaults = useThemeStore((s) => s.resetToDefaults);

  return (
    <div className="theme-settings">
      <div className="theme-settings__header">
        <span className="theme-settings__title">Appearance</span>
        <button className="theme-settings__reset" onClick={resetToDefaults}>
          Reset
        </button>
      </div>

      <div className="theme-settings__section">
        <div className="theme-settings__label">Accent Color</div>
        <div className="theme-settings__swatches">
          {ACCENT_PRESETS.map((p) => (
            <button
              key={p.hex}
              className={`theme-settings__swatch${accentColor === p.hex ? ' theme-settings__swatch--active' : ''}`}
              style={{ background: p.hex }}
              onClick={() => setAccentColor(p.hex)}
              title={p.label}
            />
          ))}
          <div className="theme-settings__custom-color" title="Custom color">
            <div className="theme-settings__custom-icon" />
            <input
              type="color"
              value={accentColor}
              onChange={(e) => setAccentColor(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="theme-settings__section">
        <div className="theme-settings__label">Status Colors</div>
        <div className="theme-settings__status-row">
          <div className="theme-settings__status-group">
            <div className="theme-settings__status-label">Success</div>
            <div className="theme-settings__swatches">
              {SUCCESS_PRESETS.map((hex) => (
                <button
                  key={hex}
                  className={`theme-settings__swatch theme-settings__swatch--small${successColor === hex ? ' theme-settings__swatch--active' : ''}`}
                  style={{ background: hex }}
                  onClick={() => setSuccessColor(hex)}
                />
              ))}
            </div>
          </div>
          <div className="theme-settings__status-group">
            <div className="theme-settings__status-label">Error</div>
            <div className="theme-settings__swatches">
              {ERROR_PRESETS.map((hex) => (
                <button
                  key={hex}
                  className={`theme-settings__swatch theme-settings__swatch--small${errorColor === hex ? ' theme-settings__swatch--active' : ''}`}
                  style={{ background: hex }}
                  onClick={() => setErrorColor(hex)}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
