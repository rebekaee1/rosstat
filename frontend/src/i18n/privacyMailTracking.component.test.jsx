import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MAIL_TRACKING_POLICY_PUBLISHED, MailTrackingPolicyEn, MailTrackingPolicyRu } from './privacyMailTracking';

describe('раздел политики об учёте писем', () => {
  it('по умолчанию не опубликован (флаг сборки)', () => {
    expect(MAIL_TRACKING_POLICY_PUBLISHED).toBe(false);
  });

  it('русский и английский тексты отрисовываются', () => {
    const ru = render(<MailTrackingPolicyRu />);
    expect(ru.container.textContent.length).toBeGreaterThan(200);
    ru.unmount();
    const en = render(<MailTrackingPolicyEn />);
    expect(en.container.textContent.length).toBeGreaterThan(200);
    expect(/[А-Яа-яЁё]/.test(en.container.textContent)).toBe(false);
    expect(screen).toBeTruthy();
  });
});
