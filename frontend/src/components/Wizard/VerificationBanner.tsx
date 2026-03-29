/**
 * VerificationBanner — inline status shown when the plan verification agent is running.
 * Three states: checking (animated), passed (green), issues_found (amber, auto-dismissed).
 */

import './VerificationBanner.css';

type VerificationStatus = 'checking' | 'passed' | 'issues_found';

interface VerificationBannerProps {
  status: VerificationStatus;
}

export function VerificationBanner({ status }: VerificationBannerProps) {
  return (
    <div className={`verification-banner verification-banner--${status}`}>
      <div className="verification-banner__track">
        {status === 'checking' && (
          <div className="verification-banner__scan-line" />
        )}
      </div>

      <div className="verification-banner__content">
        <div className="verification-banner__icon">
          {status === 'checking' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.17 3.17l1.42 1.42M11.41 11.41l1.42 1.42M3.17 12.83l1.42-1.42M11.41 4.59l1.42-1.42"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                className="verification-banner__rays"
              />
            </svg>
          )}
          {status === 'passed' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M3.5 8.5l3 3 6-6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="verification-banner__check-path"
              />
            </svg>
          )}
          {status === 'issues_found' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 5v4M8 11h.01"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          )}
        </div>

        <span className="verification-banner__label">
          {status === 'checking' && 'Verifying plan...'}
          {status === 'passed' && 'Plan verified'}
          {status === 'issues_found' && 'Fixing issues...'}
        </span>

        {status === 'checking' && (
          <span className="verification-banner__detail">
            Checking logic, connections &amp; parameters
          </span>
        )}
        {status === 'issues_found' && (
          <span className="verification-banner__detail">
            Found issues — adjusting automatically
          </span>
        )}
      </div>
    </div>
  );
}
