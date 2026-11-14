// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import {
  PERSONAL_NEWSLETTER_POLICY_PUBLISHED,
  PersonalNewsletterPolicyEn,
  PersonalNewsletterPolicyRu,
} from './privacyPersonalNewsletter';

afterEach(cleanup);

describe('черновик раздела политики о персональной подборке (ADR-0033)', () => {
  it('по умолчанию не опубликован: показ только после проверки юристом', () => {
    expect(PERSONAL_NEWSLETTER_POLICY_PUBLISHED).toBe(false);
  });

  it('русский текст: что анализируется, отказ от подборки, сроки, IP-регион не используется', () => {
    render(<PersonalNewsletterPolicyRu />);
    const text = screen.getByTestId('privacy-personal-newsletter').textContent;
    expect(text).toContain('Для вас');
    expect(text).toContain('Письма без персональной подборки');
    expect(text).toContain('180 дней');
    expect(text).toContain('Текст поисковых запросов в профиль не');
    expect(text).toContain('по IP-адресу, для подборки не используется');
  });

  it('английский текст — зеркало русского', () => {
    render(<PersonalNewsletterPolicyEn />);
    const text = screen.getByTestId('privacy-personal-newsletter').textContent;
    expect(text).toContain('For you');
    expect(text).toContain('Emails without personal picks');
    expect(text).toContain('180 days');
    expect(text).not.toMatch(/[А-Яа-яЁё]/);
  });
});
