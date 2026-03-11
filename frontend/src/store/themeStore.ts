import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { deriveAccentVariants } from '../components/Settings/colorUtils';

const DEFAULTS = {
  accentColor: '#6366f1',
  successColor: '#22c55e',
  errorColor: '#ef4444',
};

interface ThemeState {
  accentColor: string;
  successColor: string;
  errorColor: string;
  setAccentColor: (hex: string) => void;
  setSuccessColor: (hex: string) => void;
  setErrorColor: (hex: string) => void;
  resetToDefaults: () => void;
  applyTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      ...DEFAULTS,

      setAccentColor: (hex) => {
        set({ accentColor: hex });
        get().applyTheme();
      },

      setSuccessColor: (hex) => {
        set({ successColor: hex });
        get().applyTheme();
      },

      setErrorColor: (hex) => {
        set({ errorColor: hex });
        get().applyTheme();
      },

      resetToDefaults: () => {
        set(DEFAULTS);
        get().applyTheme();
      },

      applyTheme: () => {
        const { accentColor, successColor, errorColor } = get();
        const root = document.documentElement.style;
        const vars = deriveAccentVariants(accentColor);
        for (const [prop, val] of Object.entries(vars)) {
          root.setProperty(prop, val);
        }
        root.setProperty('--color-success', successColor);
        root.setProperty('--color-error', errorColor);
      },
    }),
    {
      name: 'theme-settings',
      partialize: (state) => ({
        accentColor: state.accentColor,
        successColor: state.successColor,
        errorColor: state.errorColor,
      }),
    },
  ),
);
