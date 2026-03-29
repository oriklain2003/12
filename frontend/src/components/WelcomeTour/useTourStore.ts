/**
 * Zustand micro-store for welcome tour state.
 * Persists completion status to localStorage.
 */

import { create } from 'zustand';

const STORAGE_KEY = 'onyx12_tour_completed';

interface TourState {
  isActive: boolean;
  currentStep: number;
  hasCompleted: boolean;
  startTour: () => void;
  nextStep: (totalSteps: number) => void;
  prevStep: () => void;
  closeTour: (completed?: boolean) => void;
}

export const useTourStore = create<TourState>((set) => ({
  isActive: false,
  currentStep: 0,
  hasCompleted: localStorage.getItem(STORAGE_KEY) === 'true',

  startTour: () => set({ isActive: true, currentStep: 0 }),

  nextStep: (totalSteps: number) =>
    set((state) => {
      if (state.currentStep >= totalSteps - 1) {
        localStorage.setItem(STORAGE_KEY, 'true');
        return { isActive: false, currentStep: 0, hasCompleted: true };
      }
      return { currentStep: state.currentStep + 1 };
    }),

  prevStep: () =>
    set((state) => ({
      currentStep: Math.max(0, state.currentStep - 1),
    })),

  closeTour: (completed = false) => {
    // Always persist completion — dismissing the tour counts as completing it
    // to prevent it from re-launching and blocking cursor/pointer events.
    localStorage.setItem(STORAGE_KEY, 'true');
    set({ isActive: false, currentStep: 0, hasCompleted: true });
  },
}));
