/**
 * WizardWelcome — initial state before first message.
 * Shows heading, subheading, and 2-column grid of mission type cards.
 */

import './WizardWelcome.css';

interface MissionCard {
  title: string;
  description: string;
}

const MISSION_CARDS: MissionCard[] = [
  {
    title: 'Squawk Analysis',
    description: 'Detect emergency and special squawk codes in flight data',
  },
  {
    title: 'Geographic Monitoring',
    description: 'Filter and analyze flights within specific airspace regions',
  },
  {
    title: 'Signal Health Check',
    description: 'Identify ADS-B signal anomalies and transponder issues',
  },
  {
    title: 'Flight Tracking',
    description: 'Track specific flights and analyze their course data',
  },
  {
    title: 'Anomaly Detection',
    description: 'Find unusual patterns in flight behavior and data',
  },
  {
    title: 'General Exploration',
    description: 'Browse and filter flight data with custom criteria',
  },
];

interface WizardWelcomeProps {
  onSelect: (message: string) => void;
}

export function WizardWelcome({ onSelect }: WizardWelcomeProps) {
  return (
    <div className="wizard-welcome">
      <h1 className="wizard-welcome__heading">What do you want to analyze?</h1>
      <p className="wizard-welcome__subheading">
        Describe your idea or pick a starting point below.
      </p>
      <div className="wizard-welcome__grid">
        {MISSION_CARDS.map((card) => (
          <button
            key={card.title}
            className="wizard-welcome__card glass"
            onClick={() => onSelect(`I want to do: ${card.title} — ${card.description}`)}
            type="button"
          >
            <div className="wizard-welcome__card-title">{card.title}</div>
            <div className="wizard-welcome__card-description">{card.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
